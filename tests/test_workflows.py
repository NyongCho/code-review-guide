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

    def test_official_action_owns_repo_flag_and_emits_usage_events(self):
        cfg = sample_config('api') | {'api_budget': {'approved_usd': 5, 'max_calls': 3}}
        for document in render_workflows(cfg).values():
            for job in json.loads(document)['jobs'].values():
                for step in job.get('steps', []):
                    if step.get('uses', '').startswith('openai/codex-action@'):
                        args = json.loads(step['with']['codex-args'])
                        self.assertNotIn('--skip-git-repo-check', args,
                                         'The pinned Action already supplies this non-repeatable CLI flag')
                        self.assertIn('--json', args)

    def test_terminal_state_skips_the_unused_tail(self):
        jobs=self.workflow()['jobs']
        for i in range(15):
            previous='entry' if i==0 else f'collect_{i-1}'
            for name in (f'tests_{i}',f'inspect_{i}'):
                self.assertIn(f"needs.{previous}.outputs.terminal != 'true'",jobs[name]['if'])

    def test_checks_use_separate_protected_app_credentials(self):
        jobs=self.workflow()['jobs']
        for name,job in jobs.items():
            self.assertNotEqual(job.get('permissions',{}).get('checks'),'write')
            steps=[s for s in job['steps'] if s.get('id')=='publisher-token']
            if name in {'entry','finish'}:
                self.assertEqual(job['environment'],'review-publisher')
                self.assertEqual(len(steps),1)
                self.assertEqual(steps[0]['with']['permission-checks'],'write')
            else:self.assertFalse(steps)
