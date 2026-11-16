import json
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from runtime.review_guide.contracts import ValidationError
from runtime.review_guide.install import plan_install, apply_install
from tests.fixtures import ROOT, sample_config


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.target = Path(self.temp.name) / "project"
        self.target.mkdir()

    def install(self, bundle=ROOT):
        return apply_install(self.target, plan_install(self.target, bundle, sample_config()))

    def test_reinstall_preserves_user_edits(self):
        (self.target / "AGENTS.md").write_text("내 프로젝트 규칙\n")
        self.install()
        review = self.target / "REVIEW.md"
        review.write_text(review.read_text() + "\n내 추가 규칙\n")
        self.install()
        self.assertIn("내 추가 규칙", review.read_text())
        agents = (self.target / "AGENTS.md").read_text()
        self.assertIn("내 프로젝트 규칙", agents)
        self.assertEqual(agents.count("<!-- review-guide:start -->"), 1)

    def test_existing_pr_template_keeps_user_content(self):
        template = self.target / ".github/pull_request_template.md"
        template.parent.mkdir()
        template.write_text("My checklist\n")
        self.install()
        self.install()
        self.assertIn("My checklist", template.read_text())
        self.assertEqual(template.read_text().count("<!-- review-guide:start -->"), 1)

    def test_failed_install_rolls_back_and_has_no_manifest(self):
        from runtime.review_guide.install import _atomic_write
        calls = 0

        def fail_second(path, content):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("simulated disk failure")
            return _atomic_write(path, content)

        with patch("runtime.review_guide.install._atomic_write", side_effect=fail_second):
            with self.assertRaises(OSError):
                self.install()
        self.assertFalse((self.target / ".review/manifest.json").exists())
        self.assertFalse(any(path.is_file() for path in self.target.rglob("*")))

    def test_update_reports_conflict(self):
        bundle = Path(self.temp.name) / "bundle"
        shutil.copytree(ROOT / "templates", bundle / "templates")
        shutil.copytree(ROOT / "runtime", bundle / "runtime")
        shutil.copytree(ROOT / "schemas", bundle / "schemas")
        shutil.copytree(ROOT / "skills", bundle / "skills")
        self.install(bundle)
        target = self.target / "REVIEW.md"
        target.write_text("local replacement\n")
        source = bundle / "templates/project/REVIEW.md"
        source.write_text("upstream replacement\n")
        proposal = plan_install(self.target, bundle, sample_config())
        self.assertIn("REVIEW.md", proposal["conflicts"])
        result = apply_install(self.target, proposal)
        self.assertEqual(result["status"], "needs_human")
        self.assertEqual(target.read_text(), "local replacement\n")
        self.assertTrue((self.target / ".review/proposals").is_dir())

    def test_installed_runtime_is_independent(self):
        self.install()
        executable = self.target / ".review/bin/reviewctl.py"
        result = subprocess.run(["python3", str(executable), "validate", "--config",
                                 str(self.target / ".review/config.json")],
                                cwd=self.temp.name, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.target / ".review/schemas/model-output.schema.json").is_file())

    def test_installed_request_and_fake_model_need_no_source_bundle(self):
        from tests.test_codex import CodexTests, events
        self.install()
        root = Path(self.temp.name)
        workspace, cfg, run = CodexTests().runtime_fixture(root)
        shutil.rmtree(workspace / "policy/.review")
        shutil.copytree(self.target / ".review", workspace / "policy/.review")
        config = root / "runtime.json"
        config.write_text(json.dumps(cfg))
        (root / "run.json").write_text(json.dumps(run))
        fake = root / "codex"
        fake.write_text("#!/usr/bin/env python3\nprint(" + repr(events()) + ")\n")
        fake.chmod(0o755)
        result = subprocess.run(["python3", str(self.target / ".review/bin/reviewctl.py"), "run-codex",
                                 "--config", str(config), "--run", str(root / "run.json"),
                                 "--workspace", str(workspace), "--output", str(root / "result.json"),
                                 "--executable", str(fake)], cwd=root, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads((root / "result.json").read_text())["status"], "verified")

    def test_empty_project_remains_unverified(self):
        result = self.install()
        layers = json.loads((self.target / ".review/layers.json").read_text())
        self.assertEqual(len(layers), 7)
        self.assertTrue(all(layer["status"] != "working" for layer in layers))
        self.assertEqual(result["status"], "needs_verification")

    def test_cli_dry_run_then_apply(self):
        config = Path(self.temp.name) / "config.json"
        config.write_text(json.dumps(sample_config()))
        command = ["python3", str(ROOT / "runtime/reviewctl.py"), "install", "--target",
                   str(self.target), "--config", str(config)]
        dry = subprocess.run(command + ["--dry-run"], capture_output=True, text=True)
        self.assertEqual(dry.returncode, 0, dry.stderr)
        self.assertFalse((self.target / ".review").exists())
        applied = subprocess.run(command + ["--apply"], capture_output=True, text=True)
        self.assertEqual(applied.returncode, 0, applied.stderr)
        self.assertTrue((self.target / "REVIEW.md").exists())

    def test_rejects_symlink_target_without_writing_outside(self):
        outside = Path(self.temp.name) / "outside"
        outside.mkdir()
        (self.target / ".review").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValidationError):
            self.install()
        self.assertEqual(list(outside.iterdir()), [])

    def test_stale_proposal_does_not_overwrite_concurrent_edit(self):
        proposal = plan_install(self.target, ROOT, sample_config())
        (self.target / "REVIEW.md").write_text("edited since proposal")
        with self.assertRaises(ValidationError):
            apply_install(self.target, proposal)
        self.assertEqual((self.target / "REVIEW.md").read_text(), "edited since proposal")

    def test_preserved_local_model_setting_is_used_by_generated_action(self):
        self.install()
        path = self.target / '.review/config.json'
        cfg = json.loads(path.read_text()); cfg['model'] = 'local-reviewed-model'
        path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + '\n')
        self.install()
        workflow = json.loads((self.target/'.github/workflows/review-entry.yml').read_text())
        model = next(step for step in workflow['jobs']['api_0']['steps'] if step.get('id') == 'codex')
        self.assertEqual(model['with']['model'], '${{ steps.prepare.outputs.model }}')
