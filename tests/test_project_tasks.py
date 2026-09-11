import tempfile
import unittest
from pathlib import Path
from sparkle.projects import ProjectStore
from sparkle.project_tasks import ProjectTasks
from tests.test_projects import project_manifest


class ProjectTaskTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.projects=ProjectStore(Path(self.temp.name)/'projects.db');self.projects.create(project_manifest())
        self.tasks=ProjectTasks(self.projects)

    def change(self,task,action,revision=0,**fields):
        return self.tasks.change('sparkle_core',task,action,revision,operator='cli',**fields)

    def test_dependencies_readiness_and_completion_guard(self):
        self.change('design','create',title='Design')
        self.change('build','create',title='Build',dependencies=['design'],priority=9)
        rows=self.tasks.list('sparkle_core');self.assertFalse(rows[0]['ready']);self.assertEqual(rows[0]['blocked_by'],['design'])
        with self.assertRaises(ValueError):self.change('build','transition',1,status='running')
        with self.assertRaises(ValueError):self.projects.update('sparkle_core',{'status':'complete'},expected_version=1)
        self.change('design','transition',1,status='running')
        with self.assertRaises(ValueError):self.change('design','transition',2,status='completed')
        self.change('design','transition',2,status='completed',evidence_ref='operator:design-reviewed')
        self.assertTrue(self.tasks.list('sparkle_core')[0]['ready'])
        self.assertEqual(self.tasks.list('sparkle_core')[1]['completion_verification'],'operator_reported')

    def test_cycles_unknown_dependencies_and_stale_writes(self):
        self.change('first','create',title='First');self.change('second','create',title='Second',dependencies=['first'])
        with self.assertRaises(ValueError):self.change('first','dependencies',1,dependencies=['second'])
        with self.assertRaises(ValueError):self.change('third','create',title='Third',dependencies=['missing'])
        self.change('first','transition',1,status='running')
        with self.assertRaises(ValueError):self.change('first','transition',1,status='cancelled')
        self.assertEqual(len(self.tasks.list('sparkle_core')),2)
        self.assertEqual(len(self.tasks.history('sparkle_core')),3)

    def test_archived_project_terminal_tasks_and_operator_boundary(self):
        self.change('first','create',title='First');self.change('first','transition',1,status='cancelled')
        with self.assertRaises(ValueError):self.change('first','transition',2,status='pending')
        with self.assertRaises(ValueError):self.tasks.change('sparkle_core','other','create',0,operator='model',title='Other')
        self.projects.archive('sparkle_core',expected_version=1)
        with self.assertRaises(ValueError):self.change('other','create',title='Other')
        self.assertFalse(self.tasks.list('sparkle_core')[0]['ready'])

    def test_revision_bound_metadata_edit_changes_priority_order(self):
        self.change('first','create',title='First')
        self.change('second','create',title='Second')
        self.change('second','update',1,title='Next action',priority=10,due_at='2026-10-01T00:00:00Z')
        self.assertEqual(self.tasks.list('sparkle_core')[0]['task_id'],'second')
        self.assertEqual(self.tasks.list('sparkle_core')[0]['title'],'Next action')
        with self.assertRaises(ValueError):self.change('second','update',1,priority=0)
        with self.assertRaises(ValueError):self.change('second','update',2,priority=True)

    def test_persistence_bounds_and_content_free_audit(self):
        self.change('first','create',title='private title',due_at='2026-10-01T00:00:00Z')
        self.assertEqual(ProjectTasks(self.projects).list('sparkle_core'),self.tasks.list('sparkle_core'))
        with self.assertRaises(ValueError):self.change('other','create',title='Other',dependencies=['first']*21)
        with self.assertRaises(ValueError):self.change('other','create',title='Other',priority=True)
        self.assertNotIn('private title',str(self.tasks.history('sparkle_core')))
        with self.assertRaises(Exception):
            with self.projects.connect() as db:db.execute('DELETE FROM project_task_events')
