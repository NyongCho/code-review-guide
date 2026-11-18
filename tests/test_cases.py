import json
import tempfile
import unittest
from pathlib import Path
from runtime.review_guide.cases import propose_case, confirm_case, materialize_case, OperatorDecision
from runtime.review_guide.contracts import ValidationError
from runtime.review_guide.install import apply_install, plan_install
from runtime.review_guide.workspace import prepare_workspace
from tests.fixtures import ROOT, sample_config, sample_run, finding
from tests.git_fixture import init_repo, commit_files

class CaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        repo = self.root/'repo'; init_repo(repo)
        apply_install(repo, plan_install(repo, ROOT, sample_config()))
        base = commit_files(repo, {'src/total.py':'def total(items): return sum(items)\n'})
        head = commit_files(repo, {'src/total.py':'def total(items): return sum(set(items))\n'})
        self.snapshot = self.root/'snapshot'
        prepare_workspace(repo, base, head, self.snapshot, [])
        self.run = sample_run() | {'base_sha':base,'head_sha':head,'findings':[finding()],
                                   'intent': {'title':'Count every item','body':'Duplicates are separate items.'}}
        self.candidate = self.root/'candidate'

    def test_proposals_are_idempotent_candidates_only(self):
        case = propose_case(self.run, self.snapshot, self.candidate)
        self.assertEqual(case['status'], 'candidate')
        self.assertNotIn('answers', case)
        self.assertEqual(propose_case(self.run, self.snapshot, self.candidate), case)
        self.assertNotIn('example/project', (self.candidate/'input/context.json').read_text())

    def test_snapshot_missing_or_changed_is_rejected(self):
        (self.snapshot/'source/src/total.py').write_text('tampered')
        with self.assertRaises(ValidationError): propose_case(self.run, self.snapshot, self.candidate)

    def test_evaluation_input_preserves_commit_bound_intent_without_origin_links(self):
        self.run['intent'] = {'head_commit_message':
                             'Count every repeated amount. See https://example.test/private/pr/1'}
        propose_case(self.run, self.snapshot, self.candidate)
        context = json.loads((self.candidate/'input/context.json').read_text())
        self.assertEqual(context.get('head_commit_message'),
                         'Count every repeated amount. See [external reference omitted]')

    def test_worker_approval_json_is_rejected_even_if_fields_match(self):
        case = propose_case(self.run, self.snapshot, self.candidate)
        forged = {'actor':'human','authority':'operator','at':'2026-11-16T00:00:00Z',
                  'reason':'approved','input_digest':case['input_digest'],'answers':[finding()]}
        with self.assertRaises(ValidationError): confirm_case(self.candidate, forged, self.root/'confirmed')

    def test_confirmed_input_has_no_answers_history_or_origin(self):
        case = propose_case(self.run, self.snapshot, self.candidate)
        decision = OperatorDecision('operator', '2026-11-16T00:00:00Z', case['input_digest'],
                                    'Synthetic fixture decision', [finding() | {'evidence':'ANSWER_CANARY_ONLY'}], True, 'holdout')
        confirmed = self.root/'confirmed'
        result = confirm_case(self.candidate, decision, confirmed)
        self.assertEqual(result['status'], 'confirmed')
        worker = self.root/'worker'
        materialize_case(confirmed, worker)
        texts = '\n'.join(p.read_text() for p in worker.rglob('*') if p.is_file())
        self.assertNotIn('ANSWER_CANARY_ONLY', texts)
        self.assertFalse((worker/'case.json').exists())
        self.assertFalse((worker/'.git').exists())
        self.assertFalse((worker/'policy/.review/config.json').exists())
        self.assertNotIn(self.run['repository'], (worker/'context.json').read_text())

    def test_changed_confirmed_input_and_worker_confirmation_are_blocked(self):
        from unittest.mock import patch
        case = propose_case(self.run, self.snapshot, self.candidate)
        decision = OperatorDecision('operator','2026-11-16T00:00:00Z',case['input_digest'],'reason',[],False,'holdout')
        with patch.dict('os.environ', {'GITHUB_ACTIONS':'true'}):
            with self.assertRaises(ValidationError): confirm_case(self.candidate, decision, self.root/'bad')
        confirm_case(self.candidate, decision, self.root/'confirmed')
        (self.root/'confirmed/input/source/src/total.py').write_text('tampered')
        with self.assertRaises(ValidationError): materialize_case(self.root/'confirmed', self.root/'worker')

    def test_cli_proposes_then_requires_interactive_operator_confirmation(self):
        import subprocess
        run_path = self.root/'run.json'; run_path.write_text(json.dumps(self.run))
        command = ['python3', str(ROOT/'runtime/reviewctl.py'), 'case', 'propose', '--run', str(run_path),
                   '--snapshot', str(self.snapshot), '--output', str(self.candidate)]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        answers = self.root/'answers.json'; answers.write_text(json.dumps([finding()]))
        denied = subprocess.run(['python3', str(ROOT/'runtime/reviewctl.py'), 'case', 'confirm', '--candidate',str(self.candidate),
                                 '--answers', str(answers), '--reason', 'operator decision', '--output',str(self.root/'confirmed')],
                                input='', capture_output=True, text=True)
        self.assertNotEqual(denied.returncode, 0)
        self.assertFalse((self.root/'confirmed').exists())
