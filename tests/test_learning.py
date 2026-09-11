import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from sparkle.mastery import SkillMasteryStore
from sparkle.learning import LearningService


def curriculum():
    return {'name':'math_course','title':'Math practice','goal':'Practice arithmetic',
            'topics':[{'id':'basics','title':'Basics','lesson':'Use addition.','prerequisites':[],'skill':'arithmetic'}],
            'questions':[{'id':'addition','topic':'basics','prompt':'Two plus two?','kind':'number','options':[],
                          'answer':4,'tolerance':0,'points':2,'difficulty':1}],
            'exams':[{'id':'practice','title':'Practice','sections':[{'title':'Basics','questions':['addition']}],
                      'duration_seconds':60,'pass_percent':80,'max_attempts':3}]}


class LearningTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.skills=SkillMasteryStore(Path(self.temp.name)/'skills.db')
        self.skills.create({'name':'arithmetic','title':'Arithmetic','description':'Practice','target_level':2})
        self.learning=LearningService(self.skills);self.learning.install(curriculum(),0,operator='cli')

    def start(self):return self.learning.start('math_course','practice','learner_one',1,operator='cli')

    def test_persisted_attempt_grading_retake_and_unverified_mastery_link(self):
        attempt=self.start();self.assertNotIn('"answer":',json.dumps(attempt));self.assertNotIn('"answer":',json.dumps(self.learning.curriculum('math_course')))
        result=LearningService(self.skills).act(attempt['id'],'submit',1,operator='cli',answers={'addition':4})
        self.assertTrue(result['result']['passed']);self.assertEqual(result['result']['score_percent'],100)
        self.assertFalse(result['result']['competence_verified'])
        linked=self.learning.link_skill(attempt['id'],'arithmetic',operator='cli')
        self.assertFalse(linked['evidence']['verified']);self.assertEqual(linked['skill']['current_level'],0)
        with self.assertRaises(ValueError):self.learning.link_skill(attempt['id'],'arithmetic',operator='cli')
        self.assertNotEqual(self.start()['id'],attempt['id'])
        self.assertEqual(self.learning.progress('math_course','learner_one')['topics'][0]['next_action'],'spaced_review')

    def test_save_revision_replay_and_timeout_fail_closed(self):
        with patch('sparkle.learning.time.time',return_value=100):attempt=self.start()
        with patch('sparkle.learning.time.time',return_value=110):
            saved=self.learning.act(attempt['id'],'answer',1,operator='cli',answers={'addition':4})
            self.assertEqual(saved['revision'],2)
            with self.assertRaises(ValueError):self.learning.act(attempt['id'],'submit',1,operator='cli')
        with patch('sparkle.learning.time.time',return_value=160):
            result=self.learning.act(attempt['id'],'submit',2,operator='cli')
            self.assertEqual(result['status'],'timed_out');self.assertFalse(result['result']['passed'])
        with self.assertRaises(ValueError):self.learning.act(attempt['id'],'submit',3,operator='cli')

    def test_manual_grading_is_inconclusive_and_snapshot_survives_revision(self):
        attempt=self.start();d=curriculum();d['questions'][0].update(kind='manual',answer=None,tolerance=None)
        self.learning.install(d,1,operator='cli')
        old=self.learning.act(attempt['id'],'submit',1,operator='cli',answers={'addition':4})
        self.assertTrue(old['result']['passed'])
        new=self.learning.start('math_course','practice','learner_two',2,operator='cli')
        result=self.learning.act(new['id'],'submit',1,operator='cli',answers={'addition':'Explanation'})
        self.assertIsNone(result['result']['score_percent']);self.assertFalse(result['result']['passed'])
        self.assertEqual(result['result']['validation_status'],'INCONCLUSIVE')

    def test_operator_manual_review_is_separate_and_revision_bound(self):
        d=curriculum();d['questions'][0].update(kind='manual',answer=None,tolerance=None)
        self.learning.install(d,1,operator='cli')
        attempt=self.learning.start('math_course','practice','learner_one',2,operator='cli')
        submitted=self.learning.act(attempt['id'],'submit',1,operator='cli',answers={'addition':'Explanation'})
        reviewed=self.learning.grade_manual(attempt['id'],submitted['revision'],{'addition':{'points':2,'feedback':'Rubric met'}},operator='cli')
        self.assertTrue(reviewed['result']['passed'])
        self.assertEqual(reviewed['result']['validation_status'],'GRADED_WITH_OPERATOR_REVIEW')
        self.assertFalse(reviewed['result']['competence_verified'])
        with self.assertRaises(ValueError):self.learning.grade_manual(attempt['id'],reviewed['revision'],{'addition':{'points':0,'feedback':'Duplicate'}},operator='cli')

    def test_prerequisite_exam_is_blocked_until_current_revision_practice(self):
        d=curriculum()
        d['topics'].append({'id':'advanced','title':'Advanced','lesson':'Apply basics','prerequisites':['basics'],'skill':None})
        q=copy.deepcopy(d['questions'][0]);q.update(id='next_question',topic='advanced');d['questions'].append(q)
        exam=copy.deepcopy(d['exams'][0]);exam.update(id='advanced_exam',sections=[{'title':'Advanced','questions':['next_question']}]);d['exams'].append(exam)
        self.learning.install(d,1,operator='cli')
        with self.assertRaises(ValueError):self.learning.start('math_course','advanced_exam','learner_one',2,operator='cli')
        first=self.learning.start('math_course','practice','learner_one',2,operator='cli')
        self.learning.act(first['id'],'submit',1,operator='cli',answers={'addition':4})
        self.assertEqual(self.learning.start('math_course','advanced_exam','learner_one',2,operator='cli')['status'],'active')
        with self.skills.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM curriculum_versions').fetchone()[0],2)
            with self.assertRaises(Exception):db.execute('DELETE FROM curriculum_versions')

    def test_invalid_definition_cycles_active_duplicate_and_operator_boundary(self):
        d=curriculum();d['topics'][0]['prerequisites']=['basics']
        with self.assertRaises(ValueError):self.learning.install(d,1,operator='cli')
        self.start()
        with self.assertRaises(ValueError):self.start()
        with self.assertRaises(ValueError):self.learning.install(curriculum(),1,operator='model')
        with self.assertRaises(ValueError):self.learning.install(curriculum(),0,operator='cli')
        self.learning.archive('math_course',1,operator='cli')
        with self.assertRaises(ValueError):self.start()

    def test_wrong_answer_adaptation_and_invalid_answers(self):
        attempt=self.start()
        for value in (True,float('nan'),'four'):
            with self.assertRaises(ValueError):self.learning.act(attempt['id'],'answer',1,operator='cli',answers={'addition':value})
        result=self.learning.act(attempt['id'],'submit',1,operator='cli',answers={'addition':5})
        self.assertEqual(result['result']['score_percent'],0)
        self.assertEqual(self.learning.progress('math_course','learner_one')['topics'][0]['next_action'],'revision')
