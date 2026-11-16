import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from runtime.review_guide.contracts import (
    ValidationError, validate_config, validate_output, validate_run,
    validate_case, validate_eval_manifest, digest,
)
from tests.fixtures import ROOT, finding, output, sample_config, sample_run


class ContractTests(unittest.TestCase):
    def test_defaults_and_explicit_mode(self):
        source = sample_config()
        cfg = validate_config(source)
        self.assertEqual((cfg["max_rounds"], cfg["critical_trials"]), (3, 3))
        self.assertEqual((cfg["review_mode"], cfg["auto_merge"]), ("observe", False))
        self.assertNotIn("max_rounds", source)
        with self.assertRaises(ValidationError):
            validate_config(sample_config("automatic_fallback"))

    def test_api_requires_explicit_budget(self):
        cfg = sample_config("api")
        with self.assertRaises(ValidationError):
            validate_config(cfg)
        cfg["api_budget"] = {"approved_usd": 5, "max_calls": 12}
        self.assertEqual(validate_config(cfg)["api_budget"]["max_calls"], 12)

    def test_rejects_unsafe_configuration(self):
        for field, value in [("max_rounds", 0), ("max_rounds", True),
                             ("auto_merge", True), ("review_mode", "guess"),
                             ("test_commands", ["echo hi"]), ("api_key", "secret")]:
            with self.subTest(field=field), self.assertRaises(ValidationError):
                validate_config(sample_config() | {field: value})

    def test_finding_requires_grounded_relative_location(self):
        self.assertEqual(validate_output(output([finding()]), "bugs")["status"], "findings")
        for field, value in [("evidence", ""), ("severity", "P9"),
                             ("path", "../secret"), ("line", 0)]:
            with self.subTest(field=field), self.assertRaises(ValidationError):
                validate_output(output([finding() | {field: value}]), "bugs")

    def test_clean_status_cannot_hide_findings_or_malformed_output(self):
        for bad in [output([finding()]) | {"status": "verified"},
                    output() | {"status": "findings"}, output() | {"status": "passed"},
                    {"status": "verified"}, output() | {"approved": True}]:
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                validate_output(bad, "verify")

    def test_run_requires_input_and_provenance(self):
        self.assertEqual(validate_run(sample_run())["pr"], 1)
        for field in ("base_sha", "input_digest", "rules", "deadline_at", "auth_kind"):
            run = sample_run()
            del run[field]
            with self.subTest(field=field), self.assertRaises(ValidationError):
                validate_run(run)

    def test_case_requires_snapshot_and_confirmed_answers(self):
        case = {"schema_version": 1, "id": "duplicate", "status": "candidate",
                "input_digest": "a" * 64, "source": {"kind": "synthetic"},
                "critical": True, "split": "holdout"}
        self.assertEqual(validate_case(case)["status"], "candidate")
        with self.assertRaises(ValidationError):
            validate_case(case | {"status": "confirmed"})

    def test_eval_manifest_rejects_duplicate_trial(self):
        configs = [{"model":"old"},{"model":"new"}]
        trial = {"case_id": "duplicate", "configuration_digest": digest(configs[0]), "trial_index": 1}
        manifest = {"schema_version": 1, "corpus_digest": "a" * 64,
                    "rubric_digest": "c" * 64, "expected": [trial],
                    "configurations": {digest(c):c for c in configs}, "configuration_order":[digest(c) for c in configs]}
        validate_eval_manifest(manifest)
        with self.assertRaises(ValidationError):
            validate_eval_manifest(manifest | {"expected": [trial, trial]})

    def test_cli_reports_invalid_config_without_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            path.write_text(json.dumps(sample_config("invalid")))
            result = subprocess.run(["python3", str(ROOT / "runtime/reviewctl.py"),
                                     "validate", "--config", str(path)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
