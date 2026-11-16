import json
import unittest
from runtime.review_guide.workflows import render_workflows, selected_result
from tests.fixtures import sample_config

class WorkflowTests(unittest.TestCase):
    def workflow(self, mode='self_hosted'):
        cfg = sample_config(mode)
        if mode == 'api': cfg['api_budget'] = {'approved_usd': 5, 'max_calls': 20}
        return json.loads(render_workflows(cfg)['.github/workflows/review-entry.yml'])

    def test_both_modes_use_same_dag_and_only_selected_success_is_accepted(self):
        for mode in ('api', 'self_hosted'):
            opposite = 'self_hosted' if mode == 'api' else 'api'
            for outcome in ('success', 'failure', 'cancelled', 'skipped'):
                result = selected_result(mode, {mode: outcome, opposite: 'skipped'}, {'status': 'verified'})
                self.assertEqual(result['status'] == 'verified', outcome == 'success')
        self.assertNotEqual(selected_result('api', {'api':'skipped','self_hosted':'success'}, {})['status'], 'verified')
        self.assertEqual(set(self.workflow()['jobs']), set(self.workflow('api')['jobs']))

    def test_every_pushed_head_has_explicit_checks_and_final_review(self):
        jobs = self.workflow()['jobs']
        self.assertEqual(len([j for j in jobs if j.startswith('collect_')]), 15)
        for i in range(14):
            self.assertIn(f'collect_{i}', jobs[f'tests_{i+1}']['needs'])
            self.assertIn(f'tests_{i+1}', jobs[f'inspect_{i+1}']['needs'])
        self.assertIn('collect_14', jobs['finish']['needs'])
        for i in range(15):
            self.assertIn('always()', jobs[f'collect_{i}']['if'])
            self.assertIn('!cancelled()', jobs[f'collect_{i}']['if'])

    def test_no_pr_checkout_no_model_publisher_permissions_or_api_key_environment(self):
        wf = self.workflow()
        self.assertIn('pull_request_target', wf['on'])
        for name, job in wf['jobs'].items():
            if name.startswith(('api_', 'self_hosted_', 'tests_')):
                self.assertNotEqual(job.get('permissions', {}).get('contents'), 'write')
                self.assertNotIn('OPENAI_API_KEY', job.get('env', {}))
            for step in job.get('steps', []):
                if step.get('uses', '').startswith('actions/checkout'):
                    self.assertEqual(step['with']['ref'], '${{ github.workflow_sha }}')
                    self.assertFalse(step['with']['persist-credentials'])
                if 'uses' in step:
                    self.assertRegex(step['uses'], r'@[0-9a-f]{40}$')
        self.assertIn('review-runtime', wf['jobs']['api_0']['environment'])

    def test_public_ci_has_no_model_or_secrets(self):
        from pathlib import Path
        text = Path('.github/workflows/ci.yml').read_text()
        self.assertNotIn('secrets.', text)
        self.assertNotIn('self-hosted', text)
        self.assertIn('unittest', text)
