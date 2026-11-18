import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from runtime.review_guide.pipeline import inspect_state, test_command, collect_state
from runtime.review_guide.lifecycle import initial_state
from tests.fixtures import sample_config, sample_run, output, file_proposal
from tests.test_github import Fake, pr
from runtime.review_guide.github import GitHub, input_digest

class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.cfg = sample_config()
        self.fake = Fake()
        self.api = GitHub('unused', self.fake)
        self.state = initial_state(sample_run() | {'input_digest': input_digest(pr())}, self.cfg)

    def test_unverified_entry_isolation_blocks_all_model_calls_but_preserves_ci(self):
        state = inspect_state(self.state, self.cfg, {'status': 'passed', 'head_sha': self.state['head_sha']}, self.api)
        self.assertTrue(state['terminal'])
        self.assertEqual(state['status'], 'incomplete')
        self.assertEqual(state['ci_status'], 'passed')
        self.assertIsNone(state['next_role'])

    def test_test_failure_or_wrong_head_cannot_become_success(self):
        for result in ({'status':'failed','head_sha':self.state['head_sha']},
                       {'status':'passed','head_sha':'0'*40}, None):
            state = inspect_state(self.state, self.cfg, result, self.api)
            self.assertNotEqual(state['ci_status'], 'passed')
            self.assertTrue(state['terminal'])

    def test_tests_have_no_network_secrets_host_write_or_privilege(self):
        command = test_command(Path('/tmp/input'), ['python3', '-m', 'unittest'], 'container-name')
        joined = ' '.join(command)
        for expected in ('--network=none','--read-only','--cap-drop=ALL','no-new-privileges','readonly','65534:65534'):
            self.assertIn(expected, joined)
        self.assertNotIn('GH_TOKEN', joined)
        self.assertNotIn('OPENAI_API_KEY', joined)

    def test_selected_failed_branch_stops_pipeline(self):
        state = collect_state(self.state, self.cfg, {'self_hosted':'failure','api':'skipped'}, output(), self.api, Path('/unused'))
        self.assertTrue(state['terminal'])
        self.assertEqual(state['status'], 'incomplete')

    def test_unapplicable_patch_can_be_corrected_before_any_remote_write(self):
        from tests.git_fixture import commit_files, init_repo
        from tests.fixtures import finding
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_repo(repo)
            head = commit_files(repo, {'src/total.py': 'return sum(set(items))\n'})
            self.fake.pr['head']['sha'] = head
            cfg = self.cfg | {'auto_fix': True}
            state = initial_state(sample_run() | {'head_sha': head, 'input_digest': input_digest(self.fake.pr)}, cfg)
            state.update(phase='fix', next_role='fix', role='fix', calls=3,
                         fix_paths=['src/total.py'], open_findings=[finding()])
            whitespace = file_proposal(content='return sum(items) \n')
            for proposal in (whitespace, file_proposal(content='return sum(items)\n\n')):
                with self.subTest(proposal=proposal):
                    next_state = state
                    for _ in range(2):
                        next_state = collect_state(next_state, cfg, {'self_hosted': 'success', 'api': 'skipped'},
                                                   proposal, self.api, repo)
                        self.assertNotIn('edits', next_state)
                        if next_state['calls'] == 4:
                            self.assertEqual(next_state['next_role'], 'fix')
                            self.assertEqual(next_state['fix_format_feedback']['head_sha'], head)
                    self.assertEqual(next_state['status'], 'needs_human')
            self.assertTrue(all(method == 'GET' for method, _, _ in self.fake.requests))

    def test_edit_operations_match_original_tree_before_any_remote_write(self):
        from tests.git_fixture import commit_files, git, init_repo
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            init_repo(repo)
            (repo / 'src').mkdir()
            (repo / 'src/link').symlink_to('total.py')
            head = commit_files(repo, {'src/total.py': 'old', 'tests/existing.py': 'original test'})
            self.fake.pr['head']['sha'] = head
            cfg = self.cfg | {'auto_fix': True}
            state = initial_state(sample_run() | {'head_sha': head, 'input_digest': input_digest(self.fake.pr)}, cfg)
            state.update(phase='fix', next_role='fix', calls=3, fix_paths=['src/total.py', 'src/link'])
            for proposal in (file_proposal('tests/existing.py', operation='create'),
                             file_proposal('tests/missing.py'), file_proposal('src/link'),
                             file_proposal('tests/existing.py/nested', operation='create')):
                with self.subTest(proposal=proposal):
                    result = collect_state(state, cfg, {'self_hosted': 'success'}, proposal, self.api, repo)
                    self.assertNotEqual(result['phase'], 'publish')
                    self.assertNotEqual(result['status'], 'verified')
                    self.assertEqual(git(repo, 'rev-parse', 'HEAD'), head)
            self.assertTrue(all(method == 'GET' for method, _, _ in self.fake.requests))

    def test_artifact_commit_binds_to_current_run_while_policy_stays_separate(self):
        import json, os
        from runtime.review_guide.pipeline import ci_main
        from runtime.review_guide.contracts import ValidationError
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'trusted/.review').mkdir(parents=True)
            (root/'trusted/.review/config.json').write_text(json.dumps(self.cfg))
            env = {'GITHUB_RUN_ID':'42', 'GITHUB_RUN_ATTEMPT':'2', 'GITHUB_WORKFLOW_SHA':'a'*40}
            metadata = {'id':42, 'run_attempt':2, 'head_sha':'b'*40}
            def transport(method, path, data=None):
                self.assertEqual((method, path), ('GET', '/repos/example/project/actions/runs/42'))
                return metadata
            cwd = Path.cwd()
            try:
                os.chdir(root)
                with patch.dict(os.environ, env), patch('runtime.review_guide.pipeline.GitHub', return_value=GitHub('unused', transport)), \
                        patch('runtime.review_guide.github.download_artifact') as download:
                    ci_main('fetch-artifact', 'entry', 'input')
                    self.assertEqual(download.call_args.args[1],
                                     {'name':'42-2-entry', 'run_id':42, 'head_sha':'b'*40})
                    metadata['run_attempt'] = 3
                    with self.assertRaises(ValidationError):
                        ci_main('fetch-artifact', 'entry', 'input')
                    self.assertEqual(download.call_count, 1)
                    (root/'input').mkdir()
                    (root/'input/state.json').write_text(json.dumps(self.state | {'policy_sha':'b'*40}))
                    with self.assertRaisesRegex(ValidationError, 'trusted policy/config mismatch'):
                        ci_main('tests')
            finally:
                os.chdir(cwd)

    def test_entry_through_collect_uses_installed_cli_and_real_git_snapshot(self):
        import json, os, shutil
        from runtime.review_guide.pipeline import ci_main
        from runtime.review_guide.install import plan_install, apply_install
        from tests.fixtures import ROOT
        from tests.git_fixture import init_repo, commit_files
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); trusted = root/'trusted'; init_repo(trusted)
            cfg = sample_config() | {'allowed_actors': ['owner']}
            apply_install(trusted, plan_install(trusted, ROOT, cfg))
            head = commit_files(trusted, {'src/total.py': 'def total(items): return sum(items)\n'})
            self.fake.pr['base']['sha'] = self.fake.pr['head']['sha'] = head
            env = {'GITHUB_EVENT_PATH': str(root/'event.json'), 'GITHUB_REF': 'refs/heads/main',
                   'GITHUB_WORKFLOW_SHA': head, 'GITHUB_RUN_ID': '42', 'GITHUB_RUN_ATTEMPT': '1',
                   'GITHUB_OUTPUT': str(root/'outputs'), 'TEST_OUTCOME': 'success', 'REVIEW_CHECK_TOKEN':'fixture-app-token',
                   'SELF_HOSTED_OUTCOME': 'skipped', 'API_OUTCOME': 'skipped'}
            (root/'event.json').write_text('{"number":1}')
            original = self.fake.__call__
            def transport(method, path, data=None):
                if path.endswith('/actions/runs/42'):
                    from runtime.review_guide.pipeline import now
                    return {'created_at': '2020-01-01T00:00:00Z', 'run_started_at': now()}
                return original(method, path, data)
            cwd = Path.cwd()
            try:
                os.chdir(root)
                with patch.dict(os.environ, env), patch('runtime.review_guide.pipeline.GitHub', return_value=GitHub('unused', transport)), patch('runtime.review_guide.pipeline.fetch'):
                    ci_main('entry')
                    initial=json.loads(Path('out/state.json').read_text())
                    self.assertEqual(initial['intent']['head_commit_message'],'Count every item; preserve duplicates')
                    self.assertTrue(all(c['status']=='in_progress' for c in self.fake.checks))
                    shutil.move('out', 'input')
                    Path('test-output').mkdir()
                    Path('test-output/test-result.json').write_text(json.dumps({'status':'passed','head_sha':head}))
                    ci_main('inspect')
                    state = json.loads(Path('out/state.json').read_text())
                    self.assertTrue(state['terminal'])
                    self.assertEqual(state['ci_status'], 'passed')
                    self.assertEqual(state['calls'], 0)
                    shutil.rmtree('input'); shutil.move('out', 'input')
                    ci_main('collect')
                    self.assertEqual(json.loads(Path('out/state.json').read_text())['calls'], 0)
            finally:
                os.chdir(cwd)
