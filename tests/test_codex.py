import json
import hashlib
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from runtime.review_guide.codex import build_request, run_codex, normalize_result, normalize_action
from runtime.review_guide.contracts import ValidationError, validate_config
from tests.fixtures import ROOT, output, sample_config, sample_run


def events(result=None, usage=True):
    messages = [{"type": "thread.started", "thread_id": "fixture"}, {"type": "turn.started"},
                {"type": "item.completed", "item": {"id": "item_0", "type": "agent_message",
                                                     "text": json.dumps(result or output())}},
                {"type": "turn.completed"}]
    if usage:
        messages[-1]["usage"] = {"input_tokens": 50, "output_tokens": 12}
    return "\n".join(json.dumps(item) for item in messages)


class CodexTests(unittest.TestCase):
    def runtime_fixture(self, root):
        workspace = root / "workspace"
        resources = workspace / "policy/.review"
        shutil.copytree(ROOT / "schemas", resources / "schemas")
        shutil.copytree(ROOT / "templates/project/.review/prompts", resources / "prompts")
        (workspace / "policy/REVIEW.md").write_text("Keep duplicate items.")
        home = root / "codex-home"
        home.mkdir()
        policy = 'default_permissions="review"\nweb_search="disabled"\nproject_doc_max_bytes=0\n'
        (home / "config.toml").write_text(policy)
        report_path = root / "isolation.json"
        report_path.write_text(json.dumps({"status": "verified", "policy_digest": hashlib.sha256(policy.encode()).hexdigest(),
            "codex_version": "0.169.0", "mode": "self_hosted", "runner": "linux", "checks": {
                "secret_read_denied": True, "network_denied": True,
                "instructions_inert": True, "privilege_escalation_denied": True}}))
        cfg = sample_config() | {"isolation": {"status": "verified", "codex_home": str(home), "report_path": str(report_path)}}
        run = sample_run() | {"rules": {"REVIEW.md": hashlib.sha256(b"Keep duplicate items.").hexdigest()}}
        return workspace, cfg, run

    def test_request_reads_installed_rules_and_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace, cfg, run = self.runtime_fixture(Path(tmp))
            request = build_request("bugs", run, workspace, cfg)
            self.assertIn("Keep duplicate items.", request["prompt"])
            self.assertTrue(Path(request["schema_path"]).is_relative_to(workspace))
            self.assertNotIn("--sandbox", request["argv"])
            self.assertLessEqual(request["timeout_s"], 600)

    def test_policy_change_invalidates_isolation_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace, cfg, run = self.runtime_fixture(Path(tmp))
            (Path(cfg["isolation"]["codex_home"]) / "config.toml").write_text('default_permissions=":danger-full-access"')
            with self.assertRaises(ValidationError):
                build_request("bugs", run, workspace, cfg)

    def test_request_cli_emits_action_inputs_without_authority(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace, cfg, run = self.runtime_fixture(root)
            (root / "config.json").write_text(json.dumps(cfg))
            (root / "run.json").write_text(json.dumps(run))
            result = subprocess.run(["python3", str(ROOT / "runtime/reviewctl.py"), "request", "--config", str(root / "config.json"),
                "--run", str(root / "run.json"), "--workspace", str(workspace), "--output", str(root / "prepared")], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            public = json.loads((root / "prepared/request.json").read_text())
            self.assertNotIn("gate", public)
            self.assertTrue((root / "prepared/prompt.md").is_file())

    def test_timeout_is_incomplete(self):
        self.assertEqual(normalize_result("", None, True)["status"], "incomplete")

    def test_invalid_json_is_failed(self):
        self.assertEqual(normalize_result("invalid", 0, False)["status"], "failed")

    def test_missing_turn_completion_is_incomplete(self):
        self.assertEqual(normalize_result(events().rsplit("\n", 1)[0], 0, False)["status"], "incomplete")

    def test_missing_usage_is_unknown(self):
        result = normalize_result(events(usage=False), 0, False)
        self.assertEqual(result["status"], "verified")
        self.assertIsNone(result["usage"])

    def test_failed_action_cannot_publish_clean_model_message(self):
        self.assertEqual(normalize_action(json.dumps(output()), "failure")["status"], "failed")
        self.assertEqual(normalize_action(json.dumps(output()), "success")["status"], "verified")

    def test_auth_failure_does_not_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake = root / "codex"
            count = root / "count"
            fake.write_text("#!/usr/bin/env python3\nfrom pathlib import Path\n"
                            f"p=Path({str(count)!r});p.write_text(p.read_text()+'x' if p.exists() else 'x')\n"
                            "raise SystemExit(1)\n")
            fake.chmod(0o755)
            request = {"mode": "self_hosted", "cwd": str(root), "argv": [], "prompt": "test",
                       "codex_home": str(root / "home"), "gate": {"verified": True}}
            result = run_codex(request, fake, 2)
            self.assertEqual(result["status"], "failed")
            self.assertEqual(count.read_text(), "x")

    def test_isolation_failure_blocks_review_and_fix(self):
        for role in ("bugs", "security", "verify", "fix"):
            with self.subTest(role=role), self.assertRaises(ValidationError):
                build_request(role, sample_run() | {"role": role}, ROOT, sample_config())

    def test_process_timeout_is_enforced(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake = root / "codex"
            fake.write_text("#!/usr/bin/env python3\nimport time\ntime.sleep(30)\n")
            fake.chmod(0o755)
            result = run_codex({"mode": "self_hosted", "cwd": str(root), "argv": [], "prompt": "test",
                                "codex_home": str(root / "home"), "gate": {"verified": True}}, fake, 0.1)
            self.assertEqual(result["status"], "incomplete")

    def test_raw_request_without_gate_never_starts_process(self):
        with self.assertRaises(ValidationError):
            run_codex({"mode": "self_hosted", "cwd": "/tmp", "argv": [], "prompt": "test"}, Path("/not/executed"), 1)
