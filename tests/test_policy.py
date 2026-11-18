import hashlib
import unittest

from runtime.review_guide.policy import classify_risk, check_patch, VerifiedApproval
from runtime.review_guide.contracts import ValidationError, validate_config
from tests.fixtures import sample_config, sample_run
from tests.git_fixture import patch_file


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.cfg = validate_config(sample_config() | {"auto_fix": True})
        self.run = sample_run() | {"fix_paths": ["src/total.py", "auth/login.py"]}

    def test_sensitive_floor_cannot_be_lowered(self):
        self.assertEqual(classify_risk(["auth/login.py"], "low", self.cfg)["risk"], "high")
        self.assertNotEqual(classify_risk(["src/total.py"], None, self.cfg)["risk"], "low")

    def test_verified_scope_allows_fix_and_new_regression_test(self):
        patch = patch_file() + patch_file("tests/test_total.py", new=True)
        self.assertEqual(check_patch(patch, self.run, self.cfg, None)["status"], "verified")

    def test_extra_change_lines_after_declared_hunk_require_correction(self):
        for extra in ("+assert total([100, -25]) == 75", "\n+assert total([]) == 0", "-omitted deletion"):
            with self.subTest(extra=extra):
                patch = patch_file() + extra + "\n"
                result = check_patch(patch, self.run, self.cfg, None)
                self.assertIn("format_feedback", result)
                self.assertEqual(result["paths"], [])

    def test_consecutive_unified_file_headers_and_no_newline_marker(self):
        first = patch_file().partition("\n")[2] + "\\ No newline at end of file\n"
        second = patch_file("src/second.py").partition("\n")[2]
        run = self.run | {"fix_paths": ["src/total.py", "src/second.py"]}
        self.assertEqual(check_patch(first + second, run, self.cfg, None)["status"], "verified")

    def test_sensitive_policy_and_existing_tests_need_human(self):
        for path in ("auth/login.py", ".review/config.json", "tests/test_total.py", "src/unrelated.py"):
            with self.subTest(path=path):
                self.assertEqual(check_patch(patch_file(path), self.run, self.cfg, None)["status"], "needs_human")

    def test_colocated_existing_tests_need_human_even_when_named_in_findings(self):
        for path in ("src/test_total.py", "src/total_test.go", "src/total.test.ts", "src/__tests__/total.ts"):
            with self.subTest(path=path):
                run = self.run | {"fix_paths": [path]}
                self.assertEqual(check_patch(patch_file(path), run, self.cfg, None)["status"], "needs_human")

    def test_unsafe_and_symlink_patch_cannot_be_applied(self):
        for patch in (patch_file("../../outside"), patch_file("/tmp/outside"),
                      patch_file(new=True).replace("100644", "120000")):
            with self.subTest(patch=patch):
                self.assertNotEqual(check_patch(patch, self.run, self.cfg, None)["status"], "verified")

    def test_rename_cannot_hide_sensitive_source(self):
        patch = "diff --git a/auth/login.py b/src/login.py\nsimilarity index 100%\nrename from auth/login.py\nrename to src/login.py\n"
        self.assertEqual(check_patch(patch, self.run, self.cfg, None)["status"], "needs_human")

    def test_worker_cannot_supply_approval_claim(self):
        patch = patch_file("auth/login.py")
        claim = {**self.run, "patch_digest": hashlib.sha256(patch.encode()).hexdigest(), "actor": "owner", "verified": True}
        self.assertEqual(check_patch(patch, self.run, self.cfg, claim)["status"], "needs_human")

    def test_approval_is_bound_to_exact_inputs(self):
        patch = patch_file("auth/login.py")
        bound = {key: self.run[key] for key in ("repository", "base_sha", "head_sha", "input_digest", "policy_sha")}
        bound["patch_digest"] = hashlib.sha256(patch.encode()).hexdigest()
        approval = VerifiedApproval(binding=bound, actor="owner", source="github:123")
        self.assertEqual(check_patch(patch, self.run, self.cfg, approval)["status"], "verified")
        for key in ("head_sha", "base_sha", "input_digest", "policy_sha"):
            with self.subTest(key=key):
                changed = self.run | {key: "0" * len(self.run[key])}
                self.assertEqual(check_patch(patch, changed, self.cfg, approval)["status"], "needs_human")
