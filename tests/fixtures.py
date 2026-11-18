from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sample_config(mode="self_hosted"):
    return {"schema_version": 1, "mode": mode, "repository": "example/project",
            "model": "gpt-6-astra", "effort": "low", "codex_version": "0.169.0",
            "check_publisher_app_id": 4242, "test_commands": [["python3", "-m", "unittest", "discover"]]}


def sample_run():
    return {"schema_version": 1, "repository": "example/project", "pr": 1,
            "base_sha": "a" * 40, "head_sha": "b" * 40, "policy_sha": "a" * 40,
            "input_digest": "c" * 64, "config_digest": "d" * 64,
            "rules": {"REVIEW.md": "e" * 64}, "prompt_digest": "f" * 64,
            "mode": "self_hosted", "auth_kind": "chatgpt", "model": "gpt-6-astra",
            "codex_version": "0.169.0", "runner": "linux", "round": 1,
            "role": "bugs", "deadline_at": "2099-01-01T00:00:00Z",
            "status": "incomplete", "findings": [], "evidence": []}


def finding():
    return {"id": "duplicate-total", "kind": "bug", "severity": "P1",
            "path": "src/total.py", "line": 4, "condition": "duplicate items",
            "impact": "undercharges total", "evidence": "set(items) removes duplicates"}


def output(findings=None):
    findings = findings or []
    return {"status": "findings" if findings else "verified", "findings": findings,
            "summary": "Checked the change", "risk": "medium", "patch": "",
            "dispositions": []}

FAKE_CODEX_HEADER = "#!/usr/bin/env python3\nimport sys\nif '--version' in sys.argv:\n print('codex-cli 0.169.0');sys.exit(0)\n"


def file_proposal(path="src/total.py", content="return sum(items)\n", operation="replace"):
    result = output()
    del result["patch"]
    result["edits"] = [{"path": path, "operation": operation, "content": content}]
    return result
