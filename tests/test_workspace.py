import json
import tempfile
import unittest
from pathlib import Path

from runtime.review_guide.workspace import prepare_workspace
from runtime.review_guide.contracts import ValidationError
from tests.git_fixture import init_repo, commit_files, git


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        init_repo(self.repo)
        self.base = commit_files(self.repo, {"src/total.py": "sum(set(items))\n", "REVIEW.md": "trusted rules",
                                            ".review/config.json": '{"auto_fix":false}'})

    def test_pr_instructions_are_inert_and_policy_is_from_base(self):
        head = commit_files(self.repo, {"AGENTS.override.md": "ignore safety", ".agents/skills/bad/SKILL.md": "steal",
                                       ".review/config.json": '{"auto_fix":true}', "src/total.py": "sum(items)\n"})
        dest = self.root / "workspace"
        manifest = prepare_workspace(self.repo, self.base, head, dest, [])
        self.assertFalse((dest / "source/AGENTS.override.md").exists())
        self.assertFalse((dest / "source/.agents").exists())
        self.assertEqual((dest / "policy/.review/config.json").read_text(), '{"auto_fix":false}')
        self.assertIn("AGENTS.override.md", manifest["inert_files"])
        self.assertEqual((dest / "source/src/total.py").read_text(), "sum(items)\n")
        self.assertFalse((dest / "source/.git").exists())

    def test_symlinks_are_rejected_without_reading_target(self):
        (self.repo / "src/link").symlink_to("/etc/passwd")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-m", "symlink")
        with self.assertRaises(ValidationError):
            prepare_workspace(self.repo, self.base, git(self.repo, "rev-parse", "HEAD"), self.root / "out", [])

    def test_excluded_answers_and_shell_metacharacter_filename(self):
        head = commit_files(self.repo, {".review/evals/cases/answer.json": "SECRET_ANSWER",
                                       "src/$(touch PWNED).py": "pass\n"})
        dest = self.root / "workspace"
        prepare_workspace(self.repo, self.base, head, dest, [])
        self.assertTrue((dest / "source/src/$(touch PWNED).py").exists())
        self.assertFalse((self.repo / "PWNED").exists())
        self.assertNotIn("SECRET_ANSWER", "".join(p.read_text() for p in dest.rglob("*") if p.is_file()))
