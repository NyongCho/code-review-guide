import unittest
import contextlib
import io
import json
import tempfile
from pathlib import Path

from runtime.review_guide.lifecycle import initial_state, advance, required_checks
from runtime.review_guide.contracts import ValidationError, validate_config
from tests.fixtures import sample_config, sample_run, output, finding
from tests.git_fixture import patch_file


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.cfg = validate_config(sample_config() | {"auto_fix": True})
        self.state = initial_state(sample_run(), self.cfg)
        self.sequence = 0

    def event(self, kind, **kwargs):
        self.sequence += 1
        event = {"id": str(self.sequence), "kind": kind, "head_sha": self.state["head_sha"],
                 "at": "2026-11-16T00:00:00Z", **kwargs}
        self.state = advance(self.state, event, self.cfg)
        return self.state

    def review(self, findings=None, dispositions=None):
        findings = findings or []
        self.event("model_result", role="bugs", result=output(findings))
        self.event("model_result", role="security", result=output())
        self.event("model_result", role="verify", result=output(findings) | {"dispositions": dispositions or [
            {"id": f["id"], "decision": "confirmed", "reason": "reproduced in code"} for f in findings]})

    def fixed(self):
        self.event("model_result", role="fix", result=output() | {"patch": patch_file()})
        new_sha = str(self.state["round"]) * 40
        self.event("patch_result", result={"status": "verified", "head_sha": new_sha, "input_digest": "f" * 64})
        self.event("tests_result", passed=True)

    def test_clean_review_requires_ci(self):
        self.review()
        self.assertFalse(self.state["terminal"])
        self.event("tests_result", passed=True)
        self.assertEqual(self.state["status"], "verified")
        self.assertEqual(required_checks(self.state, self.cfg)["ci"], "success")

    def test_cli_advances_serialized_state(self):
        from runtime.review_guide.cli import main
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, value in {"config": self.cfg, "state": self.state, "event": {
                "id": "tests", "kind": "tests_result", "head_sha": self.state["head_sha"],
                "at": "2026-11-16T00:00:00Z", "passed": True}}.items():
                (root / name).write_text(json.dumps(value))
            with contextlib.redirect_stdout(io.StringIO()):
                code = main(["advance", "--config", str(root / "config"), "--state", str(root / "state"),
                             "--event", str(root / "event"), "--output", str(root / "output")])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads((root / "output").read_text())["ci_status"], "passed")

    def test_fix_requires_new_head_tests_and_fresh_review(self):
        self.review([finding()])
        self.assertEqual(self.state["next_role"], "fix")
        self.fixed()
        self.assertEqual(self.state["next_role"], "bugs")
        self.assertNotEqual(self.state["status"], "verified")
        self.review([], [{"id": finding()["id"], "decision": "resolved", "reason": "fixed in current code"}])
        self.assertEqual(self.state["status"], "verified")
        self.assertEqual(self.state["tested_head"], self.state["head_sha"])
        self.assertEqual(self.state["reviewed_head"], self.state["head_sha"])

    def test_round_three_still_requires_final_review(self):
        for i in range(1, 4):
            issue = finding() | {"id": f"issue-{i}"}
            previous = [{"id": f"issue-{i-1}", "decision": "resolved", "reason": "previous issue fixed"}] if i > 1 else []
            self.review([issue], previous + [{"id": issue["id"], "decision": "confirmed", "reason": "new issue"}])
            self.fixed()
        self.assertEqual(self.state["round"], 3)
        self.assertNotEqual(self.state["status"], "verified")
        self.review([], [{"id": "issue-3", "decision": "resolved", "reason": "fixed"}])
        self.assertEqual(self.state["status"], "verified")

    def test_repeated_failure_stops(self):
        self.review([finding()])
        self.fixed()
        self.review([finding()])
        self.assertEqual(self.state["status"], "needs_human")
        self.assertTrue(self.state["terminal"])

    def test_sensitive_fix_is_not_silently_applied(self):
        self.review([finding()])
        self.event("model_result", role="fix", result=output() | {"patch": patch_file(".review/config.json")})
        self.assertEqual(self.state["status"], "needs_human")

    def test_invalid_fixer_formats_get_one_budgeted_correction(self):
        from runtime.review_guide.codex import normalize_action
        malformed = patch_file().replace('@@ -1 +1 @@', '@@ -1 +1,8 @@')
        proposals = [
            output() | {'patch': malformed},
            normalize_action(json.dumps(output() | {'status': 'findings', 'patch': patch_file()}), 'success'),
        ]
        for proposal in proposals:
            with self.subTest(proposal=proposal['status']):
                self.state = initial_state(sample_run(), self.cfg)
                self.review([finding()])
                self.event('model_result', role='fix', result=proposal)
                self.assertEqual(self.state['next_role'], 'fix')
                self.assertTrue(self.state['fix_format_feedback'])
                self.assertNotIn('patch', self.state)
                before = self.state.copy()
                self.event('model_result', role='fix', result=proposal)
                self.assertTrue(self.state['terminal'])
                self.assertNotIn('patch', self.state)
                self.state = before
                self.fixed()
                self.assertEqual(self.state['next_role'], 'bugs')
                self.assertIsNone(self.state['reviewed_head'])

    def test_format_retry_reserves_three_calls_to_review_new_head(self):
        self.cfg = validate_config(sample_config('api') | {'auto_fix': True, 'api_budget': {'approved_usd': 5, 'max_calls': 7}})
        self.state = initial_state(sample_run() | {'mode': 'api', 'auth_kind': 'api_key'}, self.cfg)
        self.review([finding()])
        self.event('model_result', role='fix', result=output() | {'patch': patch_file().replace('@@ -1 +1 @@', '@@ -1 +1,8 @@')})
        self.assertTrue(self.state['terminal'])
        self.assertIn('budget', self.state['reason'])

    def test_later_repair_cannot_use_slots_needed_to_review_its_commit(self):
        self.cfg = validate_config(sample_config('api') | {'auto_fix': True, 'api_budget': {'approved_usd': 5, 'max_calls': 11}})
        self.state = initial_state(sample_run() | {'mode': 'api', 'auth_kind': 'api_key'}, self.cfg)
        self.review([finding()])
        self.event('model_result', role='fix', result=output() | {'patch': patch_file().replace('@@ -1 +1 @@', '@@ -1 +1,8 @@')})
        self.fixed()
        new = finding() | {'id': 'another-issue'}
        self.review([new], [{'id': finding()['id'], 'decision': 'resolved', 'reason': 'fixed'},
                            {'id': new['id'], 'decision': 'confirmed', 'reason': 'new defect'}])
        self.event('model_result', role='fix', result=output() | {'patch': patch_file()})
        self.assertTrue(self.state['terminal'])
        self.assertNotIn('patch', self.state)

    def test_verified_finding_is_not_closed_without_reason(self):
        self.event("model_result", role="bugs", result=output([finding()]))
        self.event("model_result", role="security", result=output())
        self.event("model_result", role="verify", result=output())
        self.assertEqual(self.state["status"], "incomplete")

    def test_cross_reviewer_id_collision_cannot_dismiss_unrelated_finding(self):
        self.event('tests_result',passed=True)
        self.event('model_result',role='bugs',result=output([finding()]))
        security=finding()|{'kind':'security','path':'auth/access.py','condition':'Missing ownership check','impact':'Another user can read data'}
        self.event('model_result',role='security',result=output([security]))
        if not self.state['terminal']:
            self.event('model_result',role='verify',result=output()|{'dispositions':[{'id':finding()['id'],'decision':'dismissed','reason':'Duplicate total is expected'}]})
        self.assertEqual(self.state['status'],'incomplete')
        self.assertIn('omitted',self.state['reason'])

    def test_colliding_review_ids_reach_verifier_as_separate_findings(self):
        bug = finding()
        security = bug | {'evidence': 'Independent evidence for the repeated amount bug'}
        self.event('model_result', role='bugs', result=output([bug]))
        self.event('model_result', role='security', result=output([security]))
        self.assertEqual(self.state['next_role'], 'verify')
        original = self.state['candidates']['bugs'][0]
        duplicate = self.state['candidates']['security'][0]
        self.assertNotEqual(original['id'], duplicate['id'])
        self.assertEqual(duplicate['evidence'], security['evidence'])
        self.assertEqual(security['id'], bug['id'])
        self.event('model_result', role='verify', result=output([original]) | {'dispositions': [
            {'id': original['id'], 'decision': 'confirmed', 'reason': 'Reproduced'},
            {'id': duplicate['id'], 'decision': 'dismissed', 'reason': 'Same defect as the confirmed finding'},
        ]})
        self.assertEqual(self.state['next_role'], 'fix')

    def test_observe_does_not_hide_failure(self):
        self.event("tests_result", passed=True)
        self.event("model_result", role="bugs", result=output() | {"status": "incomplete"})
        checks = required_checks(self.state, self.cfg)
        self.assertEqual(self.state["status"], "incomplete")
        self.assertEqual((checks["ci"], checks["ai"]), ("success", "neutral"))

    def test_blocking_requires_approved_policy(self):
        cfg = self.cfg | {"review_mode": "block", "blocking_approval": {"source": "example"}}
        self.assertEqual(required_checks(self.state, cfg)["ai"], "failure")

    def test_deadline_blocks_new_calls_and_pushes(self):
        self.event("tick", at="2100-01-01T00:00:00Z")
        self.assertEqual(self.state["status"], "incomplete")
        self.assertIsNone(self.state["next_role"])
        self.assertTrue(self.state["terminal"])

    def test_duplicate_event_is_idempotent_and_stale_head_stops(self):
        event = {"id": "same", "kind": "tests_result", "head_sha": self.state["head_sha"], "passed": True,
                 "at": "2026-11-16T00:00:00Z"}
        once = advance(self.state, event, self.cfg)
        self.assertEqual(advance(once, event, self.cfg), once)
        with self.assertRaises(ValidationError):
            advance(once, event | {"passed": False}, self.cfg)
        stale = advance(once, event | {"id": "new", "head_sha": "0" * 40}, self.cfg)
        self.assertEqual(stale["reason"], "stale_head")

    def test_api_budget_stops_before_next_model_call(self):
        cfg = self.cfg | {"mode": "api", "api_budget": {"approved_usd": 5, "max_calls": 1}}
        self.cfg = cfg
        self.state = initial_state(sample_run() | {"mode": "api", "auth_kind": "api_key"}, cfg)
        self.event("model_result", role="bugs", result=output())
        self.assertEqual(self.state["reason"], "model call budget exhausted")

    def test_security_review_cannot_lower_prior_high_risk(self):
        self.event('model_result', role='bugs', result=output() | {'risk':'high'})
        self.event('model_result', role='security', result=output() | {'risk':'low'})
        self.assertEqual(self.state['risk'], 'high')

    def test_duplicate_verifier_dispositions_do_not_silently_close_finding(self):
        self.event('model_result', role='bugs', result=output([finding()]))
        self.event('model_result', role='security', result=output())
        self.event('model_result', role='verify', result=output() | {'dispositions': [
            {'id': finding()['id'], 'decision':'confirmed', 'reason':'reproduced'},
            {'id': finding()['id'], 'decision':'dismissed', 'reason':'ignore'}]})
        self.assertTrue(self.state['terminal'])
        self.assertNotEqual(self.state['status'], 'verified')
