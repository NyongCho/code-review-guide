#!/usr/bin/env python3
"""Validate generated YAML with a hash-pinned development-only actionlint binary."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runtime.review_guide.workflows import render_workflows

VERSION = '1.7.12'
SHA256 = '8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8'

def main():
    cache = Path(os.environ.get('XDG_CACHE_HOME', str(Path.home()/'.cache')))/'review-guide'/f'actionlint-{VERSION}'
    if not cache.exists():
        url = f'https://github.com/rhysd/actionlint/releases/download/v{VERSION}/actionlint_{VERSION}_linux_amd64.tar.gz'
        with urllib.request.urlopen(url, timeout=30) as response:
            payload = response.read(20_000_000)
        if hashlib.sha256(payload).hexdigest() != SHA256:
            raise RuntimeError('actionlint archive checksum mismatch')
        with tarfile.open(fileobj=io.BytesIO(payload), mode='r:gz') as archive:
            executable = archive.extractfile('actionlint').read()
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(executable); cache.chmod(0o755)
    with tempfile.TemporaryDirectory() as tmp:
        config = {'schema_version':1,'mode':'self_hosted','repository':'example/project', 'model':'gpt-6-astra',
                  'effort':'low','codex_version':'0.169.0','test_commands':[['python3','-m','unittest']]}
        files = [str(ROOT/'.github/workflows/ci.yml')]
        for name, text in render_workflows(config).items():
            path = Path(tmp)/Path(name).name; path.write_text(text); files.append(str(path))
        return subprocess.run([str(cache), '-config-file', str(ROOT/'.github/actionlint.yaml'), '-shellcheck=', '-pyflakes=', *files]).returncode

if __name__ == '__main__':
    raise SystemExit(main())
