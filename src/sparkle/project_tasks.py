"""Bounded project task graph. Completion is operator-reported, not proof of execution."""
from __future__ import annotations

import json

from sparkle.storage import utc_now


class ProjectTasks:
    TRANSITIONS = {'pending':{'running','blocked','cancelled'},
                   'running':{'completed','blocked','pending','cancelled'},
                   'blocked':{'pending','cancelled'}, 'completed':set(), 'cancelled':set()}

    def __init__(self, projects):
        self.projects=projects
        with projects.connect() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS project_tasks (
                project_name TEXT NOT NULL REFERENCES projects(name), task_id TEXT NOT NULL,
                title TEXT NOT NULL, dependencies TEXT NOT NULL, status TEXT NOT NULL,
                priority INTEGER NOT NULL, due_at TEXT, revision INTEGER NOT NULL,
                evidence_ref TEXT, PRIMARY KEY(project_name,task_id));
                CREATE TABLE IF NOT EXISTS project_task_events (
                id INTEGER PRIMARY KEY, project_name TEXT NOT NULL, task_id TEXT NOT NULL,
                action TEXT NOT NULL, revision INTEGER NOT NULL, created_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS idx_task_events_project ON project_task_events(project_name,id);
                CREATE TRIGGER IF NOT EXISTS task_events_no_update BEFORE UPDATE ON project_task_events
                BEGIN SELECT RAISE(ABORT,'Task audit is append-only'); END;
                CREATE TRIGGER IF NOT EXISTS task_events_no_delete BEFORE DELETE ON project_task_events
                BEGIN SELECT RAISE(ABORT,'Task audit is append-only'); END;''')

    def _project(self,db,name):
        if not isinstance(name,str) or self.projects.NAME_PATTERN.fullmatch(name) is None:
            raise ValueError('Invalid project identity')
        row=db.execute('SELECT archived,status FROM projects WHERE name=?',(name,)).fetchone()
        if row is None:raise ValueError('Project does not exist')
        return row

    def _id(self,task_id):
        if not isinstance(task_id,str) or self.projects.NAME_PATTERN.fullmatch(task_id) is None:
            raise ValueError('Invalid task identity')

    def _rows(self,db,name):
        return {r['task_id']:dict(r)|{'dependencies':json.loads(r['dependencies'])}
                for r in db.execute('SELECT * FROM project_tasks WHERE project_name=? ORDER BY task_id',(name,))}

    def list(self,name):
        with self.projects.connect() as db:
            db.execute('BEGIN');project=self._project(db,name);rows=self._rows(db,name)
        result=[]
        for row in rows.values():
            blocked=[dep for dep in row['dependencies'] if dep not in rows or rows[dep]['status']!='completed']
            result.append(row|{'blocked_by':blocked,'ready':not project['archived'] and project['status'] not in ('blocked','complete') and row['status']=='pending' and not blocked,
                               'completion_verification':'operator_reported' if row['status']=='completed' else 'not_completed'})
        return sorted(result,key=lambda r:(-r['priority'],r['due_at'] or '9999',r['task_id']))

    def _graph(self,rows):
        visiting,visited=set(),set()
        def visit(key):
            if key in visiting:raise ValueError('Task dependency cycle')
            if key in visited:return
            if key not in rows:raise ValueError('Dependency task does not exist in this project')
            visiting.add(key)
            for dep in rows[key]['dependencies']:visit(dep)
            visiting.remove(key);visited.add(key)
        for key in rows:visit(key)

    def change(self,name,task_id,action,expected_revision,*,operator,**fields):
        self._id(task_id)
        if operator not in ('cli','local_api','authenticated_api'):raise ValueError('Operator authorization required')
        if type(expected_revision) is not int or not 0<=expected_revision<2**63-1:raise ValueError('Invalid task revision')
        allowed={'create':{'title','dependencies','priority','due_at'},'dependencies':{'dependencies'},'transition':{'status','evidence_ref'},'update':{'title','priority','due_at'}}
        if not isinstance(action,str) or action not in allowed or set(fields)-allowed[action]:raise ValueError('Unsupported task operation')
        with self.projects.connect() as db:
            db.execute('BEGIN IMMEDIATE');project=self._project(db,name)
            if project['archived'] or project['status']=='complete':raise ValueError('Project is not editable')
            rows=self._rows(db,name);previous=rows.get(task_id)
            if action=='create':
                if previous or expected_revision!=0:raise ValueError('Task already exists or revision conflicts')
                if len(rows)>=200:raise ValueError('Project task capacity reached')
                title=self.projects._text(fields.get('title'),field='task title',minimum=1,maximum=200)
                priority=fields.get('priority',0)
                if type(priority) is not int or not 0<=priority<=10:raise ValueError('Task priority must be 0 to 10')
                row={'project_name':name,'task_id':task_id,'title':title,'dependencies':[],
                     'status':'pending','priority':priority,'due_at':self.projects._timestamp(fields.get('due_at'),field='task due_at'),
                     'revision':0,'evidence_ref':None}
            else:
                if previous is None or previous['revision']!=expected_revision:raise ValueError('Task revision conflict')
                row=dict(previous)
            if action in ('create','dependencies'):
                if row['status'] not in ('pending','blocked'):raise ValueError('Only unstarted tasks can change dependencies')
                deps=fields.get('dependencies',[])
                if not isinstance(deps,list) or len(deps)>20:raise ValueError('At most 20 task dependencies allowed')
                for dep in deps:self._id(dep)
                if len(set(deps))!=len(deps):raise ValueError('Duplicate task dependency')
                row['dependencies']=sorted(deps);rows[task_id]=row;self._graph(rows)
            elif action=='update':
                if not fields or row['status'] in ('completed','cancelled'):
                    raise ValueError('Only nonterminal task metadata can be edited')
                if 'title' in fields:
                    row['title']=self.projects._text(fields['title'],field='task title',minimum=1,maximum=200)
                if 'priority' in fields:
                    if type(fields['priority']) is not int or not 0<=fields['priority']<=10:
                        raise ValueError('Task priority must be 0 to 10')
                    row['priority']=fields['priority']
                if 'due_at' in fields:
                    row['due_at']=self.projects._timestamp(fields['due_at'],field='task due_at')
            else:
                status=fields.get('status')
                if not isinstance(status,str) or status not in self.TRANSITIONS[row['status']]:raise ValueError('Illegal task transition')
                if status in ('running','completed') and (project['status']=='blocked' or any(rows[d]['status']!='completed' for d in row['dependencies'])):
                    raise ValueError('Task dependencies or project are blocked')
                if status=='completed':
                    row['evidence_ref']=self.projects._text(fields.get('evidence_ref'),field='completion evidence reference',minimum=1,maximum=256)
                elif fields.get('evidence_ref') is not None:raise ValueError('Completion evidence requires completed state')
                row['status']=status
            row['revision']+=1
            if db.execute('SELECT COUNT(*) FROM project_task_events WHERE project_name=?',(name,)).fetchone()[0]>=10000:raise ValueError('Task audit capacity reached')
            db.execute('''INSERT INTO project_tasks VALUES(?,?,?,?,?,?,?,?,?)
                ON CONFLICT(project_name,task_id) DO UPDATE SET title=excluded.title,priority=excluded.priority,
                due_at=excluded.due_at,dependencies=excluded.dependencies,
                status=excluded.status,revision=excluded.revision,evidence_ref=excluded.evidence_ref''',
                (name,task_id,row['title'],json.dumps(row['dependencies']),row['status'],row['priority'],row['due_at'],row['revision'],row['evidence_ref']))
            db.execute('INSERT INTO project_task_events(project_name,task_id,action,revision,created_at) VALUES(?,?,?,?,?)',
                       (name,task_id,action,row['revision'],utc_now()))
        return row

    def history(self,name):
        with self.projects.connect() as db:
            self._project(db,name)
            return [dict(r) for r in db.execute('SELECT * FROM project_task_events WHERE project_name=? ORDER BY id DESC LIMIT 100',(name,))]
