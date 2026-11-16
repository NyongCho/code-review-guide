import copy
import io
import json
import subprocess
import time
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from runtime.review_guide.ssh_worker import pack_request, serve_request, run_remote
from runtime.review_guide.contracts import ValidationError
from tests import test_codex
from tests.fixtures import output, ROOT, FAKE_CODEX_HEADER


class SSHWorkerTests(unittest.TestCase):
    def fixture(self, root):
        workspace,cfg,run=test_codex.CodexTests().runtime_fixture(root)
        server={'schema_version':1,'allowed_repositories':[cfg['repository']], 'allowed_models':[cfg['model']],
                'allowed_efforts':['low'],'codex_version':cfg['codex_version'],'codex_executable':'/operator/pinned/codex',
                'work_root':str(root/'server-work'),'codex_home':cfg['isolation']['codex_home'],
                'report_path':cfg['isolation']['report_path'],'max_timeout_s':60}
        return workspace,cfg,run,server

    def test_server_uses_own_runtime_authority_and_removes_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);workspace,cfg,run,server=self.fixture(root)
            cfg['isolation']={'status':'verified','codex_home':'/attacker','report_path':'/attacker/report'}
            calls=[]
            def execute(request,executable,timeout_s):
                calls.append(request)
                self.assertEqual(str(executable),server['codex_executable'])
                self.assertEqual(request['codex_home'],server['codex_home'])
                self.assertLessEqual(timeout_s,60)
                self.assertTrue(Path(request['cwd']).is_relative_to(Path(server['work_root'])/'active-input'))
                return output()
            result=serve_request(pack_request(run,cfg,workspace),server,execute)
            self.assertEqual(result['status'],'verified')
            self.assertEqual(len(calls),1)
            self.assertFalse((Path(server['work_root'])/'active-input').exists())

    def test_wrong_repo_mode_model_or_version_stops_before_model_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace,cfg,run,server=self.fixture(Path(tmp))
            called=[]
            for bad in (cfg|{'repository':'evil/project'}, cfg|{'model':'unapproved'},cfg|{'codex_version':'0.118.0'},
                        cfg|{'mode':'api','api_budget':{'approved_usd':5,'max_calls':3}}):
                with self.subTest(bad=bad['model']),self.assertRaises(ValidationError):
                    serve_request(pack_request(run,bad,workspace),server,lambda *a:called.append(a))
            self.assertEqual(called,[])

    def test_zip_traversal_or_symlink_cannot_write_outside_worker_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);_,cfg,run,server=self.fixture(root)
            for name,symlink in [('../escape',False),('workspace/link',True)]:
                raw=io.BytesIO()
                with zipfile.ZipFile(raw,'w') as archive:
                    archive.writestr('request.json',json.dumps({'run':run,'config':cfg}))
                    info=zipfile.ZipInfo(name)
                    if symlink:info.external_attr=(0o120777<<16)
                    archive.writestr(info,'outside')
                with self.assertRaises(ValidationError):serve_request(raw.getvalue(),server,lambda *a:output())
            self.assertFalse((root/'escape').exists())

    def test_expired_request_or_stale_workspace_does_not_start_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);workspace,cfg,run,server=self.fixture(root)
            with self.assertRaises(ValidationError):
                serve_request(pack_request(run|{'deadline_at':'2000-01-01T00:00:00Z'},cfg,workspace),server,lambda *a:output())
            active=Path(server['work_root'])/'active-input';active.mkdir(parents=True)
            (active/'operator-evidence').write_text('keep')
            with self.assertRaises(ValidationError):serve_request(pack_request(run,cfg,workspace),server,lambda *a:output())
            self.assertEqual((active/'operator-evidence').read_text(),'keep')

    def test_run_identity_cannot_disagree_with_selected_model(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace,cfg,run,server=self.fixture(Path(tmp))
            for bad in (run|{'model':'other'},run|{'effort':'high'}):
                with self.assertRaises(ValidationError):
                    serve_request(pack_request(bad,cfg,workspace),server,lambda *a:output())

    def test_malformed_archive_is_a_validation_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            _,_,_,server=self.fixture(Path(tmp))
            with self.assertRaises(ValidationError):serve_request(b'not zip',server)

    def test_remote_client_to_forced_command_and_clean_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);workspace,cfg,run,server=self.fixture(root)
            fake_model=root/'model'
            fake_model.write_text(FAKE_CODEX_HEADER+'import sys\nsys.stdin.read()\nprint('+repr(test_codex.events())+')\n')
            fake_model.chmod(0o755);server['codex_executable']=str(fake_model)
            config=root/'server.json';config.write_text(json.dumps(server))
            fake_ssh=root/'ssh';audit=root/'audit.json'
            fake_ssh.write_text('#!/usr/bin/python3\nimport sys,os,json,subprocess\n'
                +'from pathlib import Path\n'
                +f'Path({str(audit)!r}).write_text(json.dumps({{"argv":sys.argv,"env":dict(os.environ)}}))\n'
                +f'r=subprocess.run(["python3",{str(ROOT/"runtime/reviewctl.py")!r},"serve","--server-config",{str(config)!r}],input=sys.stdin.buffer.read(),capture_output=True)\n'
                +'sys.stdout.buffer.write(r.stdout);sys.stderr.buffer.write(r.stderr);raise SystemExit(r.returncode)\n')
            fake_ssh.chmod(0o755)
            connection={'host':'worker.example','user':'review-worker','private_key':'synthetic','known_hosts':'synthetic'}
            result=run_remote(run,cfg,workspace,connection,str(fake_ssh))
            self.assertEqual(result['status'],'verified',result)
            evidence=json.loads(audit.read_text())
            self.assertEqual(evidence['argv'][-1],'review-worker@worker.example')
            self.assertIn('StrictHostKeyChecking=yes',evidence['argv'])
            self.assertNotIn('GH_TOKEN',evidence['env'])
            self.assertNotIn('REVIEW_SSH_KEY',evidence['env'])
            key=Path(evidence['argv'][evidence['argv'].index('-i')+1])
            self.assertFalse(key.exists())
            blocked=subprocess.run(['python3',str(ROOT/'runtime/reviewctl.py'),'serve','--server-config',str(config)],
                input=b'',capture_output=True,env=os.environ|{'SSH_ORIGINAL_COMMAND':'bash'})
            self.assertEqual(blocked.returncode,2)
            self.assertIn(b'SSH commands are not accepted',blocked.stderr)

    def test_remote_output_limit_stops_before_process_finishes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);workspace,cfg,run,_=self.fixture(root)
            fake=root/'ssh'
            fake.write_text('#!/usr/bin/python3\nimport sys,time\nsys.stdin.buffer.read()\nsys.stderr.write("x"*3000000)\nsys.stderr.flush()\ntime.sleep(3)\n')
            fake.chmod(0o755)
            started=time.monotonic()
            result=run_remote(run,cfg,workspace,{'host':'worker.example','user':'review','private_key':'fake','known_hosts':'fake'},str(fake))
            self.assertEqual(result['status'],'failed')
            self.assertLess(time.monotonic()-started,2)
