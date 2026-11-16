import copy
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from runtime.review_guide.github import (GitHub, input_digest, run_key, verify_current, verify_entry,
                                        resolve_approval, publish_result, verify_archive)
from runtime.review_guide.contracts import ValidationError, digest
from runtime.review_guide.lifecycle import initial_state
from tests.fixtures import sample_config, sample_run


def pr():
    return {'number': 1, 'state': 'open', 'title': 'Count every item', 'body': 'Keep duplicates',
            'user': {'login': 'owner', 'type': 'User'},
            'base': {'sha': 'a'*40, 'ref': 'main', 'repo': {'full_name': 'example/project', 'private': True}},
            'head': {'sha': 'b'*40, 'ref': 'feature', 'repo': {'full_name': 'example/project'}}}


class Fake:
    def __init__(self):
        self.pr = pr()
        self.comments, self.checks = [], []
        self.requests = []
        self.approval = {'id': 17, 'event': 'workflow_dispatch', 'path': '.github/workflows/review-approve.yml',
                         'head_sha': 'a'*40, 'head_branch': 'main', 'conclusion': 'success',
                         'actor': {'login': 'owner', 'type': 'User'},
                         'triggering_actor': {'login': 'owner', 'type': 'User'}}
        self.job = {'name': 'approve-' + digest({'head_sha': 'b'*40}), 'conclusion': 'success'}
    def __call__(self, method, path, data=None):
        self.requests.append((method, path, data))
        if '/pulls/1' in path: return copy.deepcopy(self.pr)
        if '/actions/workflows/' in path: return {'workflow_runs': []}
        if '/permission' in path: return {'permission': 'admin'}
        if path.endswith('/runs/17'): return self.approval
        if '/runs/17/jobs?' in path: return {'jobs': [self.job], 'total_count': 1}
        if '/issues/1/comments' in path:
            if method == 'GET': return self.comments
            obj = {'id': len(self.comments)+1, 'user': {'type': 'Bot', 'login': 'github-actions[bot]'}, **data}; self.comments.append(obj); return obj
        if '/issues/comments/' in path: self.comments[0].update(data); return self.comments[0]
        if path.endswith('/check-runs') or '/check-runs?' in path:
            if method == 'GET': return {'check_runs': self.checks, 'total_count': len(self.checks)}
            obj = {'id': len(self.checks)+1, 'app': {'slug': 'github-actions'}, **data}; self.checks.append(obj); return obj
        if '/check-runs/' in path:
            obj = next(c for c in self.checks if c['id'] == int(path.rsplit('/',1)[1])); obj.update(data); return obj
        raise AssertionError((method, path, data))


class GitHubTests(unittest.TestCase):
    def setUp(self):
        self.fake = Fake()
        self.api = GitHub('unused', self.fake)
        self.run = sample_run() | {'input_digest': input_digest(self.fake.pr)}

    def test_key_includes_base_and_intent(self):
        self.assertNotEqual(run_key(self.run), run_key(self.run | {'base_sha': '0'*40}))
        self.assertNotEqual(run_key(self.run), run_key(self.run | {'input_digest': '0'*64}))

    def test_entry_requires_private_same_repo_author_and_trusted_ref(self):
        cfg = sample_config() | {'allowed_actors': ['owner']}
        verify_entry(self.fake.pr, cfg, 'refs/heads/main')
        self.fake.pr['base']['repo']['private'] = False
        with self.assertRaises(ValidationError): verify_entry(self.fake.pr, cfg, 'refs/heads/main')
        self.fake.pr = pr()
        with self.assertRaises(ValidationError): verify_entry(self.fake.pr, cfg, 'refs/heads/feature')
        self.fake.pr['head']['repo']['full_name'] = 'fork/project'
        with self.assertRaises(ValidationError): verify_entry(self.fake.pr, cfg, 'refs/heads/main')

    def test_stale_head_base_and_intent(self):
        for field, value, reason in [('head', '0'*40, 'stale_head'), ('base', '0'*40, 'stale_input')]:
            current = pr(); current[field]['sha'] = value
            self.assertEqual(verify_current(self.run, current)['reason'], reason)
        current = pr(); current['body'] = 'Different intent'
        self.assertEqual(verify_current(self.run, current)['reason'], 'stale_input')

    def test_publication_is_idempotent_and_does_not_hide_incomplete(self):
        state = initial_state(self.run, sample_config())
        state.update(terminal=True, status='incomplete', ci_status='passed', tested_head=state['head_sha'])
        for _ in range(2): publish_result(state, sample_config(), self.api)
        self.assertEqual(len(self.fake.comments), 1)
        self.assertEqual(len(self.fake.checks), 3)
        by_name = {c['name']: c for c in self.fake.checks}
        self.assertEqual(by_name['review-guide/ci']['head_sha'], state['head_sha'])
        self.assertEqual(by_name['review-guide/ci']['conclusion'], 'success')
        self.assertEqual(by_name['review-guide/human']['conclusion'], 'failure')
        self.assertEqual(self.fake.checks[0]['conclusion'], 'neutral')
        self.assertIn('incomplete', self.fake.comments[0]['body'])
        self.fake.pr['head']['sha'] = '0'*40
        self.assertEqual(publish_result(state, sample_config(), self.api)['reason'], 'stale_head')

    def test_worker_cannot_forge_approval(self):
        expected = {'head_sha': 'b'*40}
        ref = {'repository': 'example/project', 'run_id': 17, 'policy_sha': 'a'*40, 'trusted_branch': 'main'}
        approval = resolve_approval(ref, expected, self.api)
        self.assertEqual(approval.actor, 'owner')
        self.fake.approval['event'] = 'pull_request'
        with self.assertRaises(ValidationError): resolve_approval(ref, expected, self.api)
        self.fake.approval['event'] = 'workflow_dispatch'
        self.fake.job['name'] = 'approve-' + digest({'head_sha': '0'*40})
        with self.assertRaises(ValidationError): resolve_approval(ref, expected, self.api)

    def test_artifact_identity_digest_and_paths(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive: archive.writestr('result.json', '{}')
        payload = stream.getvalue()
        import hashlib
        expected = {'run_id': 19, 'head_sha': 'a'*40, 'name': 'worker-19-1-bugs'}
        meta = {'workflow_run': {'id': 19, 'head_sha': 'a'*40}, 'name': expected['name'],
                'digest': 'sha256:' + hashlib.sha256(payload).hexdigest(), 'expired': False}
        with tempfile.TemporaryDirectory() as tmp:
            verify_archive(payload, meta, expected, Path(tmp)/'ok')
            self.assertEqual((Path(tmp)/'ok/result.json').read_text(), '{}')
            with self.assertRaises(ValidationError):
                verify_archive(payload, meta, expected | {'run_id': 20}, Path(tmp)/'bad')
            stream = io.BytesIO()
            with zipfile.ZipFile(stream, 'w') as archive: archive.writestr('../escape', 'x')
            payload = stream.getvalue(); meta['digest'] = 'sha256:' + hashlib.sha256(payload).hexdigest()
            with self.assertRaises(ValidationError): verify_archive(payload, meta, expected, Path(tmp)/'bad')

class PatchTests(unittest.TestCase):
    def test_patch_retry_recovers_lost_push_response_without_second_commit(self):
        from runtime.review_guide.github import publish_patch
        from tests.git_fixture import init_repo, commit_files, patch_file, git
        from runtime.review_guide.contracts import validate_config
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)/'repo'; init_repo(repo)
            head = commit_files(repo, {'src/total.py': 'return sum(set(items))\n'})
            fixed = commit_files(repo, {'src/total.py': 'return sum(items)\n'})
            expected_tree = git(repo, 'rev-parse', fixed + '^{tree}')
            current = pr(); current['base']['sha'] = current['head']['sha'] = head
            run = sample_run() | {'base_sha': head, 'head_sha': head, 'input_digest': input_digest(current),
                                  'fix_paths': ['src/total.py'], 'created_at': '2026-11-16T00:00:00Z'}
            cfg = validate_config(sample_config() | {'auto_fix': True})
            commits, patches = [], []
            def transport(method, path, data=None):
                if '/pulls/1' in path: return copy.deepcopy(current)
                if '/git/commits/' in path:
                    return commits[0] if commits and path.endswith(commits[0]['sha']) else {'tree': {'sha': head}}
                if path.endswith('/git/blobs'):
                    import base64, hashlib
                    raw = base64.b64decode(data['content'])
                    return {'sha': hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()}
                if path.endswith('/git/trees'): return {'sha': expected_tree}
                if path.endswith('/git/commits'):
                    commits.append(data | {'sha': 'f'*40}); return commits[0]
                if '/git/refs/heads/' in path:
                    patches.append(data); current['head']['sha'] = data['sha']
                    raise OSError('response lost')
                raise AssertionError((method, path))
            api = GitHub('unused', transport)
            first = publish_patch(run, patch_file(), cfg, repo, api)
            second = publish_patch(run, patch_file(), cfg, repo, api)
            self.assertEqual(first['status'], 'verified')
            self.assertEqual(second, first)
            self.assertEqual(len(commits), 1)
            self.assertEqual(len(patches), 1)
            self.assertFalse(patches[0]['force'])
            commits[0]['tree'] = '0'*40
            forged = publish_patch(run, patch_file(), cfg, repo, api)
            self.assertEqual(forged['reason'], 'stale_head')

    def test_expired_run_cannot_push(self):
        from runtime.review_guide.github import publish_patch
        fake = Fake()
        state = sample_run() | {'deadline_at': '2000-01-01T00:00:00Z'}
        result = publish_patch(state, '', sample_config(), Path('/unused'), GitHub('unused', fake))
        self.assertEqual(result['status'], 'incomplete')
        self.assertEqual(fake.requests, [])
