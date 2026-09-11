"""Stateful authored curricula and bounded assessments; no claim of proctored mastery."""
from __future__ import annotations

import hashlib
import json
import math
import re
import time
import uuid
from datetime import UTC, datetime


IDENTIFIER = re.compile(r'[a-z][a-z0-9_-]{1,63}\Z')


def ident(value):
    if not isinstance(value,str) or IDENTIFIER.fullmatch(value) is None:
        raise ValueError('Invalid learning identity')
    return value


def text(value,limit):
    if not isinstance(value,str) or not value.strip() or len(value)>limit:
        raise ValueError('Invalid or oversized learning text')
    return value.strip()


def finite_number(value):
    try:
        return type(value) in (int,float) and math.isfinite(value)
    except (OverflowError,ValueError):
        return False


def encoded(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)


class LearningService:
    def __init__(self,skills):
        self.skills=skills
        with skills.connect() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS curricula (
                name TEXT PRIMARY KEY, revision INTEGER NOT NULL, archived INTEGER NOT NULL,
                definition TEXT NOT NULL, digest TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS curriculum_versions (
                name TEXT NOT NULL, revision INTEGER NOT NULL, definition TEXT NOT NULL,
                digest TEXT NOT NULL, archived INTEGER NOT NULL, PRIMARY KEY(name,revision));
                INSERT OR IGNORE INTO curriculum_versions SELECT name,revision,definition,digest,archived FROM curricula;
                CREATE TRIGGER IF NOT EXISTS curriculum_versions_no_update BEFORE UPDATE ON curriculum_versions
                BEGIN SELECT RAISE(ABORT,'Curriculum versions are immutable'); END;
                CREATE TRIGGER IF NOT EXISTS curriculum_versions_no_delete BEFORE DELETE ON curriculum_versions
                BEGIN SELECT RAISE(ABORT,'Curriculum versions are immutable'); END;
                CREATE TABLE IF NOT EXISTS learning_attempts (
                id TEXT PRIMARY KEY, learner TEXT NOT NULL, course TEXT NOT NULL, exam TEXT NOT NULL,
                course_revision INTEGER NOT NULL, snapshot TEXT NOT NULL, answers TEXT NOT NULL,
                status TEXT NOT NULL, revision INTEGER NOT NULL, started REAL NOT NULL,
                deadline REAL NOT NULL, finished REAL, result TEXT);
                CREATE UNIQUE INDEX IF NOT EXISTS one_active_learning_attempt
                ON learning_attempts(learner,course,exam) WHERE status='active';
                CREATE INDEX IF NOT EXISTS learning_attempt_owner ON learning_attempts(learner,course,started);
                CREATE TABLE IF NOT EXISTS learning_events (
                id INTEGER PRIMARY KEY, subject TEXT NOT NULL, action TEXT NOT NULL,
                revision INTEGER NOT NULL, created REAL NOT NULL);
                CREATE INDEX IF NOT EXISTS learning_events_subject ON learning_events(subject,id);
                CREATE TRIGGER IF NOT EXISTS learning_events_no_update BEFORE UPDATE ON learning_events
                BEGIN SELECT RAISE(ABORT,'Learning audit is append-only'); END;
                CREATE TRIGGER IF NOT EXISTS learning_events_no_delete BEFORE DELETE ON learning_events
                BEGIN SELECT RAISE(ABORT,'Learning audit is append-only'); END;''')

    @staticmethod
    def _operator(operator):
        if operator not in ('cli','local_api','authenticated_api'):
            raise ValueError('Operator authorization required')

    @staticmethod
    def _revision(value):
        if type(value) is not int or not 0<=value<2**63-1:
            raise ValueError('Invalid expected revision')

    @staticmethod
    def _event(db,subject,action,revision):
        if db.execute('SELECT COUNT(*) FROM learning_events WHERE subject=?',(subject,)).fetchone()[0]>=10000:
            raise ValueError('Learning audit capacity reached')
        db.execute('INSERT INTO learning_events(subject,action,revision,created) VALUES(?,?,?,?)',
                   (subject,action,revision,time.time()))

    @staticmethod
    def validate(definition):
        if not isinstance(definition,dict) or set(definition)!={'name','title','goal','topics','questions','exams'}:
            raise ValueError('Curriculum requires name, title, goal, topics, questions and exams')
        d=json.loads(encoded(definition));ident(d['name']);text(d['title'],200);text(d['goal'],2000)
        for field,maximum in (('topics',50),('questions',200),('exams',20)):
            if not isinstance(d[field],list) or not 1<=len(d[field])<=maximum:
                raise ValueError('Curriculum collection bound exceeded')
        topics={}
        for topic in d['topics']:
            if not isinstance(topic,dict) or set(topic)!={'id','title','lesson','prerequisites','skill'}:
                raise ValueError('Invalid topic fields')
            ident(topic['id']);text(topic['title'],200);text(topic['lesson'],10000)
            if topic['id'] in topics:raise ValueError('Duplicate topic')
            if topic['skill'] is not None:ident(topic['skill'])
            deps=topic['prerequisites']
            if not isinstance(deps,list) or len(deps)>10:raise ValueError('Invalid prerequisites')
            for dep in deps:ident(dep)
            if len(set(deps))!=len(deps):raise ValueError('Duplicate prerequisite')
            topics[topic['id']]=topic
        visiting,done=set(),set()
        def visit(key):
            if key not in topics:raise ValueError('Missing prerequisite topic')
            if key in visiting:raise ValueError('Curriculum prerequisite cycle')
            if key in done:return
            visiting.add(key)
            for dep in topics[key]['prerequisites']:visit(dep)
            visiting.remove(key);done.add(key)
        for key in topics:visit(key)
        questions={}
        for q in d['questions']:
            if not isinstance(q,dict) or set(q)!={'id','topic','prompt','kind','options','answer','tolerance','points','difficulty'}:
                raise ValueError('Invalid question fields')
            ident(q['id']);text(q['prompt'],4000)
            if q['id'] in questions or q['topic'] not in topics:raise ValueError('Invalid question identity/topic')
            if type(q['points']) is not int or not 1<=q['points']<=100:raise ValueError('Invalid question points')
            if type(q['difficulty']) is not int or not 1<=q['difficulty']<=5:raise ValueError('Invalid question difficulty')
            if q['kind'] not in ('choice','number','text','manual'):raise ValueError('Unsupported question kind')
            if q['kind']=='choice':
                if not isinstance(q['options'],list) or not 2<=len(q['options'])<=8:raise ValueError('Invalid choice options')
                for option in q['options']:text(option,1000)
                if len(set(q['options']))!=len(q['options']) or q['answer'] not in q['options']:raise ValueError('Invalid choice answer')
            elif q['options']!=[]:raise ValueError('Only choice questions accept options')
            if q['kind']=='number':
                for value in (q['answer'],q['tolerance']):
                    if not finite_number(value):raise ValueError('Invalid numeric key')
                if not 0<=q['tolerance']<=1000000:raise ValueError('Invalid numeric tolerance')
            elif q['tolerance'] is not None:raise ValueError('Only numeric questions accept tolerance')
            if q['kind']=='text':text(q['answer'],4000)
            if q['kind']=='manual' and q['answer'] is not None:raise ValueError('Manual questions have no automatic key')
            questions[q['id']]=q
        exams=set()
        for exam in d['exams']:
            if not isinstance(exam,dict) or set(exam)!={'id','title','sections','duration_seconds','pass_percent','max_attempts'}:
                raise ValueError('Invalid exam fields')
            ident(exam['id']);text(exam['title'],200)
            if exam['id'] in exams:raise ValueError('Duplicate exam')
            exams.add(exam['id'])
            for key,lo,hi in (('duration_seconds',1,7200),('pass_percent',1,100),('max_attempts',1,20)):
                if type(exam[key]) is not int or not lo<=exam[key]<=hi:raise ValueError('Invalid exam limit')
            if not isinstance(exam['sections'],list) or not 1<=len(exam['sections'])<=10:raise ValueError('Invalid sections')
            ids=[]
            for section in exam['sections']:
                if not isinstance(section,dict) or set(section)!={'title','questions'}:raise ValueError('Invalid section')
                text(section['title'],200)
                if not isinstance(section['questions'],list) or not 1<=len(section['questions'])<=100:raise ValueError('Invalid section question count')
                for key in section['questions']:
                    ident(key)
                    if key not in questions:raise ValueError('Unknown exam question')
                    ids.append(key)
            if len(ids)>100 or len(set(ids))!=len(ids):raise ValueError('Duplicate or oversized exam questions')
        if len(encoded(d).encode('utf-8'))>1000000:raise ValueError('Curriculum exceeds byte bound')
        return d

    def install(self,definition,expected_revision,*,operator):
        self._operator(operator);self._revision(expected_revision);d=self.validate(definition)
        payload=encoded(d);digest=hashlib.sha256(payload.encode()).hexdigest()
        with self.skills.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT revision FROM curricula WHERE name=?',(d['name'],)).fetchone()
            if (old['revision'] if old else 0)!=expected_revision:raise ValueError('Curriculum revision conflict')
            if old is None and db.execute('SELECT COUNT(*) FROM curricula').fetchone()[0]>=100:
                raise ValueError('Curriculum capacity reached')
            for topic in d['topics']:
                if topic['skill'] is not None and db.execute('SELECT 1 FROM skills WHERE name=? AND archived=0',(topic['skill'],)).fetchone() is None:
                    raise ValueError('Linked skill must exist and be active')
            revision=expected_revision+1
            db.execute('INSERT INTO curricula VALUES(?,?,0,?,?) ON CONFLICT(name) DO UPDATE SET revision=excluded.revision,archived=0,definition=excluded.definition,digest=excluded.digest',
                       (d['name'],revision,payload,digest))
            db.execute('INSERT INTO curriculum_versions VALUES(?,?,?,?,0)',(d['name'],revision,payload,digest))
            self._event(db,d['name'],'installed',revision)
        return {'name':d['name'],'revision':revision,'digest':digest}

    def courses(self):
        with self.skills.connect() as db:rows=db.execute('SELECT * FROM curricula ORDER BY name LIMIT 100').fetchall()
        return [{'name':r['name'],'revision':r['revision'],'archived':bool(r['archived']),'digest':r['digest'],
                 'title':json.loads(r['definition'])['title'],'goal':json.loads(r['definition'])['goal']} for r in rows]

    @staticmethod
    def _course(db,name):
        ident(name);row=db.execute('SELECT * FROM curricula WHERE name=?',(name,)).fetchone()
        if row is None:raise ValueError('Curriculum is missing')
        if hashlib.sha256(row['definition'].encode()).hexdigest()!=row['digest']:
            raise ValueError('Curriculum digest mismatch')
        return row,json.loads(row['definition'])

    def curriculum(self,name):
        with self.skills.connect() as db:row,d=self._course(db,name)
        # Answer keys never leave through curriculum/agent read interfaces.
        d['questions']=[{k:v for k,v in q.items() if k not in ('answer','tolerance')} for q in d['questions']]
        with self.skills.connect() as db:
            versions=[dict(r) for r in db.execute('SELECT revision,digest,archived FROM curriculum_versions WHERE name=? ORDER BY revision DESC LIMIT 100',(name,))]
        return d|{'revision':row['revision'],'archived':bool(row['archived']),'versions':versions}

    def archive(self,name,expected_revision,*,operator):
        self._operator(operator);self._revision(expected_revision)
        with self.skills.connect() as db:
            db.execute('BEGIN IMMEDIATE');row,_=self._course(db,name)
            if row['revision']!=expected_revision or row['archived']:raise ValueError('Curriculum revision conflict')
            db.execute('UPDATE curricula SET archived=1,revision=revision+1 WHERE name=?',(name,))
            db.execute('INSERT INTO curriculum_versions VALUES(?,?,?,?,1)',(name,expected_revision+1,row['definition'],row['digest']))
            self._event(db,name,'archived',expected_revision+1)
        return {'name':name,'archived':True,'revision':expected_revision+1}

    @staticmethod
    def _attempt(db,attempt_id):
        if not isinstance(attempt_id,str) or re.fullmatch('[a-f0-9]{32}',attempt_id) is None:raise ValueError('Invalid attempt identity')
        row=db.execute('SELECT * FROM learning_attempts WHERE id=?',(attempt_id,)).fetchone()
        if row is None:raise ValueError('Attempt is missing')
        return dict(row)

    def start(self,course,exam,learner,expected_revision,*,operator):
        self._operator(operator);ident(learner);ident(exam);self._revision(expected_revision)
        with self.skills.connect() as db:
            db.execute('BEGIN IMMEDIATE');row,d=self._course(db,course)
            if row['archived'] or row['revision']!=expected_revision:raise ValueError('Curriculum unavailable or stale')
            spec=next((e for e in d['exams'] if e['id']==exam),None)
            if spec is None:raise ValueError('Exam is missing')
            prior=db.execute('SELECT * FROM learning_attempts WHERE learner=? AND course=? AND exam=?',(learner,course,exam)).fetchall()
            for attempt in prior:
                if attempt['status']=='active':
                    if time.time()>=attempt['deadline']:self._finish(db,dict(attempt),'timed_out')
                    else:raise ValueError('An active attempt already exists')
            if len(prior)>=spec['max_attempts']:raise ValueError('Exam attempt limit reached')
            if db.execute('SELECT COUNT(*) FROM learning_attempts').fetchone()[0]>=10000:raise ValueError('Learning attempt capacity reached')
            keys=[k for section in spec['sections'] for k in section['questions']]
            question_map={q['id']:q for q in d['questions']}
            tested_topics={question_map[key]['topic'] for key in keys}
            progress=self.progress(course,learner)
            if any(set(t['blocked_by'])-tested_topics for t in progress['topics'] if t['topic'] in tested_topics):
                raise ValueError('Exam prerequisites require practice first')
            snapshot={'exam':spec,'questions':[question_map[key] for key in keys],
                      'topics':d['topics'],'course_digest':row['digest']}
            attempt_id=uuid.uuid4().hex;now=time.time()
            db.execute('INSERT INTO learning_attempts VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',
                (attempt_id,learner,course,exam,row['revision'],encoded(snapshot),'{}','active',1,now,now+spec['duration_seconds'],None,None))
            self._event(db,attempt_id,'started',1)
        return self.inspect(attempt_id)

    @staticmethod
    def _grade(snapshot,answers):
        checks=[];earned=0;possible=0;unknown=False
        for q in snapshot['questions']:
            value=answers.get(q['id']);possible+=q['points']
            if q['kind']=='manual':correct=None;unknown=True
            elif q['kind']=='number':correct=finite_number(value) and abs(value-q['answer'])<=q['tolerance']
            elif q['kind']=='text':correct=isinstance(value,str) and value.strip()==q['answer'].strip()
            else:correct=value==q['answer']
            points=q['points'] if correct is True else 0;earned+=points
            checks.append({'question_id':q['id'],'topic':q['topic'],'correct':correct,'earned':points,'possible':q['points']})
        score=None if unknown else round(100*earned/possible,6)
        return {'score_percent':score,'earned':earned,'possible':possible,'checks':checks,
                'validation_status':'INCONCLUSIVE' if unknown else 'GRADED_AGAINST_AUTHORED_KEY',
                'passed':score is not None and score>=snapshot['exam']['pass_percent'],'competence_verified':False}

    def _finish(self,db,row,status):
        result=self._grade(json.loads(row['snapshot']),json.loads(row['answers']))
        if status!='submitted':result['passed']=False
        db.execute('UPDATE learning_attempts SET status=?,revision=revision+1,finished=?,result=? WHERE id=?',
                   (status,time.time(),encoded(result),row['id']))
        self._event(db,row['id'],status,row['revision']+1)

    def act(self,attempt_id,action,expected_revision,*,operator,answers=None):
        self._operator(operator);self._revision(expected_revision)
        if action not in ('answer','submit','cancel'):raise ValueError('Invalid attempt action')
        with self.skills.connect() as db:
            db.execute('BEGIN IMMEDIATE');row=self._attempt(db,attempt_id)
            if row['status']!='active' or row['revision']!=expected_revision:raise ValueError('Attempt state/revision conflict')
            if time.time()<row['started']:raise ValueError('Attempt clock regression')
            if time.time()>=row['deadline']:self._finish(db,row,'timed_out')
            elif action=='cancel':
                if answers is not None:raise ValueError('Cancellation does not accept answers')
                self._finish(db,row,'cancelled')
            else:
                current=json.loads(row['answers']);snapshot=json.loads(row['snapshot'])
                if answers is not None:
                    if not isinstance(answers,dict) or len(answers)>100:raise ValueError('Invalid answer set')
                    questions={q['id']:q for q in snapshot['questions']}
                    for key,value in answers.items():
                        if key not in questions:raise ValueError('Unknown answer identity')
                        q=questions[key]
                        if q['kind']=='number':
                            if not finite_number(value):raise ValueError('Numeric answer required')
                        elif not isinstance(value,str) or len(value)>4000:raise ValueError('Bounded text answer required')
                        if q['kind']=='choice' and value not in q['options']:raise ValueError('Unknown choice')
                    current.update(answers)
                if action=='answer' and answers is None:raise ValueError('Answers required')
                row['answers']=encoded(current)
                db.execute('UPDATE learning_attempts SET answers=? WHERE id=?',(row['answers'],attempt_id))
                if action=='submit':self._finish(db,row,'submitted')
                else:
                    db.execute('UPDATE learning_attempts SET revision=revision+1 WHERE id=?',(attempt_id,))
                    self._event(db,attempt_id,'answers_saved',row['revision']+1)
        return self.inspect(attempt_id)

    def inspect(self,attempt_id):
        with self.skills.connect() as db:
            db.execute('BEGIN IMMEDIATE');row=self._attempt(db,attempt_id)
            if row['status']=='active' and time.time()>=row['deadline']:
                self._finish(db,row,'timed_out');row=self._attempt(db,attempt_id)
            events=[dict(e) for e in db.execute('SELECT action,revision,created FROM learning_events WHERE subject=? ORDER BY id DESC LIMIT 100',(attempt_id,))]
        row['events']=events
        snapshot=json.loads(row.pop('snapshot'));row['answers']=json.loads(row['answers'])
        row['result']=json.loads(row['result']) if row['result'] else None
        row['questions']=[{k:v for k,v in q.items() if k not in ('answer','tolerance')} for q in snapshot['questions']]
        row['sections']=snapshot['exam']['sections'];row['course_digest']=snapshot['course_digest']
        return row

    def progress(self,course,learner):
        ident(learner)
        with self.skills.connect() as db:
            row,d=self._course(db,course)
            attempts=db.execute("SELECT id,status,result,exam,started,deadline,course_revision FROM learning_attempts WHERE course=? AND learner=? ORDER BY started DESC LIMIT 400",(course,learner)).fetchall()
        latest={}
        for attempt in attempts:
            if attempt['status']!='submitted' or attempt['course_revision']!=row['revision']:continue
            result=json.loads(attempt['result']);by_topic={}
            for check in result['checks']:by_topic.setdefault(check['topic'],[]).append(check)
            for topic,checks in by_topic.items():
                if topic not in latest:
                    latest[topic]=None if any(c['correct'] is None for c in checks) else sum(c['earned'] for c in checks)/sum(c['possible'] for c in checks)
        topics=[]
        for topic in d['topics']:
            score=latest.get(topic['id']);blocked=[dep for dep in topic['prerequisites'] if (latest.get(dep) or 0)<0.8]
            topics.append({'topic':topic['id'],'skill':topic['skill'],'latest_practice_fraction':score,'blocked_by':blocked,
                           'next_action':'prerequisite_practice' if blocked else 'initial_practice' if score is None else 'revision' if score<0.8 else 'spaced_review',
                           'competence_verified':False})
        return {'course':course,'learner':learner,'topics':topics,'attempts':[{'id':a['id'],'exam':a['exam'],'status':a['status'],'course_revision':a['course_revision'],
                    'started':a['started'],'deadline':a['deadline'],'overdue':a['status']=='active' and time.time()>=a['deadline'],
                    'score_percent':json.loads(a['result'])['score_percent'] if a['result'] else None} for a in attempts],
                'policy':'latest current-revision authored-key practice; readiness threshold 0.8; not mastery proof'}

    def link_skill(self,attempt_id,skill_name,*,operator):
        self._operator(operator);ident(skill_name);row=self.inspect(attempt_id)
        if row['status']!='submitted' or row['result']['score_percent'] is None:raise ValueError('A fully graded submitted attempt is required')
        with self.skills.connect() as db:
            original=self._attempt(db,attempt_id);snapshot=json.loads(original['snapshot'])
        topics={t['id'] for t in snapshot['topics'] if t['skill']==skill_name}
        checks=[c for c in row['result']['checks'] if c['topic'] in topics]
        if not checks:raise ValueError('Exam does not assess this linked skill')
        return self.skills.add_evidence({'skill_name':skill_name,'evidence_type':'test',
            'score':round(100*sum(c['earned'] for c in checks)/sum(c['possible'] for c in checks)),
            'verified':False,'summary':'Authored-key practice result; identity and competence not independently verified',
            'artifact_ref':'learning-attempt:'+attempt_id,'occurred_at':datetime.fromtimestamp(row['finished'],UTC).isoformat()})

    def grade_manual(self,attempt_id,expected_revision,grades,*,operator):
        self._operator(operator);self._revision(expected_revision)
        if not isinstance(grades,dict) or not 1<=len(grades)<=100:raise ValueError('Manual grades required')
        with self.skills.connect() as db:
            db.execute('BEGIN IMMEDIATE');row=self._attempt(db,attempt_id)
            if row['status']!='submitted' or row['revision']!=expected_revision:raise ValueError('Attempt state/revision conflict')
            snapshot=json.loads(row['snapshot']);result=json.loads(row['result'])
            questions={q['id']:q for q in snapshot['questions']};checks={c['question_id']:c for c in result['checks']}
            for key,grade in grades.items():
                if key not in questions or questions[key]['kind']!='manual' or checks[key]['correct'] is not None:
                    raise ValueError('Only ungraded manual questions accept review')
                if not isinstance(grade,dict) or set(grade)!={'points','feedback'}:raise ValueError('Points and feedback required')
                points=grade['points']
                if type(points) is not int or not 0<=points<=checks[key]['possible']:raise ValueError('Manual points out of range')
                feedback=text(grade['feedback'],1000)
                checks[key].update(earned=points,correct=points==checks[key]['possible'],review_method='operator',feedback=feedback)
            result['earned']=sum(c['earned'] for c in checks.values())
            unknown=any(c['correct'] is None for c in checks.values())
            result['score_percent']=None if unknown else round(100*result['earned']/result['possible'],6)
            result['validation_status']='INCONCLUSIVE' if unknown else 'GRADED_WITH_OPERATOR_REVIEW'
            result['passed']=not unknown and result['score_percent']>=snapshot['exam']['pass_percent']
            db.execute('UPDATE learning_attempts SET revision=revision+1,result=? WHERE id=?',(encoded(result),attempt_id))
            self._event(db,attempt_id,'manual_review',expected_revision+1)
        return self.inspect(attempt_id)


    def stats(self):
        with self.skills.connect() as db:
            return {'curricula':db.execute('SELECT COUNT(*) FROM curricula').fetchone()[0],
                    'attempts':db.execute('SELECT COUNT(*) FROM learning_attempts').fetchone()[0],
                    'competence_verified':False}
