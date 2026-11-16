import subprocess
from pathlib import Path


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True,
                          text=True, check=True).stdout.strip()


def init_repo(path: Path):
    path.mkdir(exist_ok=True)
    git(path, "init", "-b", "main")
    git(path, "config", "user.name", "Test")
    git(path, "config", "user.email", "test@example.invalid")


def commit_files(repo: Path, files: dict[str, str]):
    for name, text in files.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    git(repo, "add", ".")
    git(repo, "commit", "-m", "fixture")
    return git(repo, "rev-parse", "HEAD")


def patch_file(path="src/total.py", new=False):
    if new:
        return f"diff --git a/{path} b/{path}\nnew file mode 100644\n--- /dev/null\n+++ b/{path}\n@@ -0,0 +1 @@\n+assert total([1, 1]) == 2\n"
    return f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n@@ -1 +1 @@\n-return sum(set(items))\n+return sum(items)\n"
