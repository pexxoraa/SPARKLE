"""Prove handle closure while retaining references and disabling garbage collection."""
import contextlib
import gc
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from benchmarks.agents import run_agents
from sparkle.ai_system_builder import AISystemBlueprintStore
from sparkle.storage import ClosingConnection, SQLiteStore, StorageConnectionError
from sparkle.system import SparkleSystem


def fd_count():
    if os.name != "posix":
        raise unittest.SkipTest("Descriptor enumeration requires POSIX")
    import fcntl
    import resource
    # The isolated low-limit probe scans its entire descriptor range.
    ceiling=min(resource.getrlimit(resource.RLIMIT_NOFILE)[0],4096)
    total=0
    for fd in range(ceiling):
        try: fcntl.fcntl(fd,fcntl.F_GETFD);total+=1
        except OSError: pass
    return total


@contextlib.contextmanager
def tracked_connections(factory=ClosingConnection):
    retained=[]
    real=sqlite3.connect
    enabled=gc.isenabled();gc.disable()
    def connect(*args,**kwargs):
        kwargs['factory']=factory
        connection=real(*args,**kwargs);retained.append(connection)
        return connection
    try:
        with patch('sparkle.storage.sqlite3.connect',side_effect=connect):yield retained
    finally:
        # Inspectors retain strong references; GC cannot supply the tested close.
        for connection in retained:connection.close()
        if enabled:gc.enable()


def assert_closed(test,connections):
    test.assertTrue(connections)
    for connection in connections:
        with test.assertRaises(sqlite3.ProgrammingError):sqlite3.Connection.execute(connection,'SELECT 1')


class StorageResourceTests(unittest.TestCase):
    def test_store_scopes_close_and_backup_closes_both_handles(self):
        with tempfile.TemporaryDirectory() as directory,tracked_connections() as connections:
            store=SQLiteStore(Path(directory)/'store.db')
            with store.connect() as connection:connection.execute('CREATE TABLE t(v)')
            store.backup(Path(directory)/'copy.db')
            assert_closed(self,connections)

    def test_each_setup_pragma_failure_closes_before_context_entry(self):
        for pragma in ('PRAGMA journal_mode=WAL','PRAGMA foreign_keys=ON'):
            class Failing(ClosingConnection):
                def execute(self,sql,*args):
                    if sql==pragma:raise sqlite3.OperationalError('private path must not appear')
                    return super().execute(sql,*args)
            with self.subTest(pragma=pragma),tempfile.TemporaryDirectory() as directory,tracked_connections(Failing) as connections:
                before=fd_count()
                for i in range(20):
                    with self.assertRaises(StorageConnectionError) as caught:
                        SQLiteStore(Path(directory)/f'{i}.db').connect()
                    self.assertEqual(caught.exception.to_dict()['error_type'],'storage_unavailable')
                    self.assertNotIn('private',str(caught.exception))
                    assert_closed(self,connections)
                self.assertEqual(fd_count(),before)

    def test_interrupt_during_connection_setup_also_closes(self):
        class Interrupted(ClosingConnection):
            def execute(self,*args):raise KeyboardInterrupt()
        with tempfile.TemporaryDirectory() as directory,tracked_connections(Interrupted) as connections:
            with self.assertRaises(KeyboardInterrupt):SQLiteStore(Path(directory)/'store.db').connect()
            assert_closed(self,connections)

    def test_late_system_initialization_failure_closes_all_previous_stores(self):
        def fail(store):
            with store.connect() as connection:
                connection.execute('CREATE TABLE t(v)')
                raise sqlite3.OperationalError('synthetic initialization failure')
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,{'SPARKLE_DATA_DIR':directory}),tracked_connections() as connections:
            before=fd_count()
            with patch.object(AISystemBlueprintStore,'initialize',fail):
                with self.assertRaises(sqlite3.OperationalError):SparkleSystem()
            self.assertGreater(len(connections),10)
            assert_closed(self,connections)
            self.assertEqual(fd_count(),before)

    def test_repeated_system_setup_no_fd_growth_with_systems_retained(self):
        with tempfile.TemporaryDirectory() as directory,tracked_connections() as connections:
            before=fd_count();systems=[]
            for i in range(6):
                with patch.dict(os.environ,{'SPARKLE_DATA_DIR':str(Path(directory)/str(i))}):systems.append(SparkleSystem())
                assert_closed(self,connections)
                self.assertEqual(fd_count(),before)
        self.assertFalse(Path(directory).exists())

    def test_completed_benchmark_closes_every_connection_before_temp_cleanup(self):
        with tracked_connections() as connections:
            before=fd_count()
            with tempfile.TemporaryDirectory() as directory:
                report=run_agents(Path(directory))
                self.assertEqual(report['task_count'],12)
                self.assertEqual(report['pass_rate'],1)
                assert_closed(self,connections)
                self.assertEqual(fd_count(),before)
            self.assertFalse(Path(directory).exists())

    def test_failed_benchmark_setup_closes_connections_before_cleanup(self):
        with tracked_connections() as connections:
            before=fd_count()
            with tempfile.TemporaryDirectory() as directory:
                with patch.object(AISystemBlueprintStore,'initialize',side_effect=StorageConnectionError()):
                    with self.assertRaises(StorageConnectionError):run_agents(Path(directory))
                assert_closed(self,connections)
                self.assertEqual(fd_count(),before)
            self.assertFalse(Path(directory).exists())

    def test_provider_failed_benchmark_releases_every_database(self):
        from tests.test_provider_deadline import TimeoutAdapter
        with tracked_connections() as connections:
            before=fd_count()
            with tempfile.TemporaryDirectory() as directory:
                report=run_agents(Path(directory),adapter_factory=TimeoutAdapter)
                self.assertEqual(report['failure_categories'],{'provider_timeout':12})
                assert_closed(self,connections)
                self.assertEqual(fd_count(),before)
            self.assertFalse(Path(directory).exists())

    @unittest.skipUnless(os.name=='posix','Descriptor inheritance check requires POSIX')
    def test_database_descriptors_are_not_inheritable(self):
        import fcntl
        def descriptors():
            result=set()
            for fd in range(4096):
                try:fcntl.fcntl(fd,fcntl.F_GETFD);result.add(fd)
                except OSError:pass
            return result
        with tempfile.TemporaryDirectory() as directory:
            before=descriptors()
            with SQLiteStore(Path(directory)/'store.db').connect() as connection:
                connection.execute('CREATE TABLE t(v)')
                opened=descriptors()-before
                self.assertTrue(opened)
                self.assertTrue(all(not os.get_inheritable(fd) for fd in opened))
            self.assertEqual(descriptors(),before)

    @unittest.skipUnless(os.name=='posix','FD limits require POSIX')
    def test_real_low_fd_limit_has_no_growth_and_structured_exhaustion(self):
        completed=subprocess.run([sys.executable,'-m','tests.test_storage_resources','--fd-probe'],capture_output=True,text=True,timeout=30)
        self.assertEqual(completed.returncode,0,completed.stderr)
        report=json.loads(completed.stdout)
        self.assertEqual(report['before'],report['after'])
        self.assertEqual(report['error']['error_type'],'storage_unavailable')
        self.assertTrue(report['cleanup'])


def low_fd_probe():
    import resource
    soft,hard=resource.getrlimit(resource.RLIMIT_NOFILE)
    resource.setrlimit(resource.RLIMIT_NOFILE,(min(32,hard),hard))
    gc.disable()
    before=fd_count()
    with tempfile.TemporaryDirectory() as directory:
        for i in range(10):
            with patch.dict(os.environ,{'SPARKLE_DATA_DIR':str(Path(directory)/str(i))}):SparkleSystem()
            assert fd_count()==before
        occupied=[]
        try:
            while True:
                try:occupied.append(os.open(os.devnull,os.O_RDONLY))
                except OSError:break
            try:SQLiteStore(Path(directory)/'exhausted.db').connect()
            except StorageConnectionError as exc:error=exc.to_dict()
            else:raise AssertionError('FD exhaustion not reached')
        finally:
            for fd in occupied:os.close(fd)
        assert fd_count()==before
    print(json.dumps({'before':before,'after':fd_count(),'error':error,'cleanup':not Path(directory).exists()}))


if __name__=='__main__':
    if '--fd-probe' in sys.argv:low_fd_probe()
    else:unittest.main()
