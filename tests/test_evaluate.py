import copy
import unittest
from runtime.review_guide.evaluate import build_eval_manifest, compare_runs, JudgedTrial, seal_trial, open_trial
from runtime.review_guide.contracts import digest, ValidationError
from tests.fixtures import finding, output


def case(name, critical, answers):
    return {'schema_version':1,'id':name,'input_digest':digest(name),'source':{},'status':'confirmed',
            'critical':critical,'split':'holdout','answers':answers,
            'decision':{'actor':'fixture operator','at':'2026-11-16T00:00:00Z','reason':'fixture',
                        'authority':'local-operator','input_digest':digest(name)}}


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.cases = [case('bug', True, [finding()]), case('clean', False, [])]
        self.configs = [{'model':m,'tools_digest':digest('same tools'),'rules_digest':digest('same rules')}
                        for m in ('incumbent','candidate')]
        self.rubric = {'version':1,'critical_trials':3}
        self.manifest = build_eval_manifest(self.cases, self.configs, self.rubric)
        self.baseline, self.candidate = [], []
        for trial in self.manifest['expected']:
            bug = trial['case_id']=='bug'
            findings = [finding()] if bug else []
            record = trial | {'corpus_digest':self.manifest['corpus_digest'],'rubric_digest':digest(self.rubric),
                              'input_digest':digest(trial['case_id']), 'status':'complete',
                              'tools_digest':digest('same tools'),'rules_digest':digest('same rules'),
                              'stages':{'bugs':output(findings),'security':output(),'verify':output(findings)},
                              'elapsed_s':1.0,'usage':None}
            matches = {finding()['id']:finding()['id']} if bug else {}
            judgment = {'actor':'fixture operator','at':'2026-11-16T00:00:00Z','reason':'semantic inspection',
                        'matches':{'bugs':matches,'security':{},'verify':matches},'extras':{}}
            target = self.baseline if trial['configuration_digest']==digest(self.configs[0]) else self.candidate
            target.append(JudgedTrial(record, judgment))

    def compare(self, baseline=None, candidate=None):
        return compare_runs(self.manifest, self.baseline if baseline is None else baseline,
                            self.candidate if candidate is None else candidate, self.rubric)

    def test_frozen_configuration_contents_must_match_digest(self):
        candidate_id=self.manifest['configuration_order'][1]
        self.manifest['configurations'][candidate_id]['model']='unapproved-third-model'
        with self.assertRaises(ValidationError):self.compare()

    def test_critical_three_trials_and_eligible_still_requires_human(self):
        self.assertEqual(len(self.manifest['expected']), 8)
        report = self.compare()
        self.assertEqual(report['decision'], 'eligible_for_human_review')
        self.assertEqual(report['expected_count'], 8)
        self.assertEqual(report['completion_rate'], 1)
        self.assertIsNone(report['metrics'][digest(self.configs[1])]['usage'])

    def test_missing_duplicate_unknown_trials_hold_without_changing_denominator(self):
        unknown = copy.deepcopy(self.candidate[0]); unknown.record['trial_index']=99
        for rows in (self.candidate[:-1], self.candidate+[self.candidate[0]], self.candidate+[unknown]):
            report = self.compare(candidate=rows)
            self.assertEqual(report['decision'], 'hold')
            self.assertEqual(report['expected_count'], 8)
        self.assertEqual(self.compare(candidate=self.candidate[:-1])['completion_rate'], 7/8)

    def test_verifier_drop_and_any_critical_miss_hold(self):
        rows = copy.deepcopy(self.candidate)
        rows[0].record['stages']['verify'] = output()
        rows[0].judgment['matches']['verify'] = {}
        report = self.compare(candidate=rows)
        self.assertEqual(report['decision'], 'hold')
        metric = report['metrics'][digest(self.configs[1])]
        self.assertEqual(metric['detected'], 3)
        self.assertEqual(metric['critical_misses'], 1)

    def test_unfamiliar_clean_finding_is_pending_not_false_positive(self):
        rows = copy.deepcopy(self.candidate)
        clean = next(r for r in rows if r.record['case_id']=='clean')
        clean.record['stages']['verify'] = output([finding()])
        report = self.compare(candidate=rows)
        metric = report['metrics'][digest(self.configs[1])]
        self.assertEqual(metric['pending'], 1)
        self.assertEqual(metric['false_positives'], 0)
        self.assertEqual(report['decision'], 'hold')

    def test_conditions_and_incomplete_trials_hold(self):
        for field, value in [('corpus_digest','0'*64),('tools_digest','0'*64),('status','incomplete')]:
            rows = copy.deepcopy(self.candidate); rows[0].record[field]=value
            self.assertEqual(self.compare(candidate=rows)['decision'], 'hold')

    def test_worker_cannot_forge_judgment_receipt(self):
        key = b'operator-only key'
        sealed = seal_trial(self.candidate[0], key)
        opened = open_trial(sealed, key)
        self.assertEqual(opened.record, self.candidate[0].record)
        sealed['judgment']['actor']='forged'
        with self.assertRaises(ValidationError): open_trial(sealed, key)
        with self.assertRaises(ValidationError): open_trial(seal_trial(self.candidate[0], key), b'wrong key')
        self.assertEqual(self.compare(candidate=[r.record for r in self.candidate])['decision'], 'hold')

    def test_manifest_rejects_different_tools_and_candidates(self):
        configs = copy.deepcopy(self.configs); configs[1]['tools_digest']=digest('more tools')
        with self.assertRaises(ValidationError): build_eval_manifest(self.cases, configs, self.rubric)
        self.cases[0]['status']='candidate'
        with self.assertRaises(ValidationError): build_eval_manifest(self.cases, self.configs, self.rubric)

    def test_malformed_trial_keeps_fixed_denominator(self):
        rows=copy.deepcopy(self.candidate)
        rows[0].record.pop('trial_index')
        result=self.compare(candidate=rows)
        self.assertEqual(result['decision'],'hold')
        self.assertEqual(result['expected_count'],8)
