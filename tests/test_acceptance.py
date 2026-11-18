"""Synthetic end-to-end acceptance: real Git and tests, fake model/GitHub transport.

Operator decisions and isolation reports below are fixtures, not deployment evidence.
"""
from tests.fixtures import FAKE_CODEX_HEADER
import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from runtime.review_guide.cases import OperatorDecision, confirm_case, materialize_case, propose_case
from runtime.review_guide.codex import build_request, normalize_action, run_codex
from runtime.review_guide.contracts import digest, validate_config
from runtime.review_guide.evaluate import JudgedTrial, build_eval_manifest, compare_runs
from runtime.review_guide.github import GitHub, input_digest, publish_patch, publish_result
from runtime.review_guide.lifecycle import initial_state
from runtime.review_guide.pipeline import collect_state, inspect_state
from runtime.review_guide.policy import check_patch, classify_risk
from runtime.review_guide.workspace import prepare_workspace
from tests.fixtures import ROOT, sample_config, sample_run, output, finding
from tests.git_fixture import init_repo, commit_files, git
from tests import test_codex, test_github


class GitTransport(test_github.Fake):
    def __init__(self, repo, base):
        super().__init__(); self.repo=repo; self.base=base; self.created_commits=0; self.pushes=0
    def execute(self,*args,input=None,env=None):
        return subprocess.run(['git','-C',str(self.repo),*args],input=input,env=env,capture_output=True,check=True).stdout.decode().strip()
    def __call__(self,method,path,data=None):
        self.pr['base']['sha']=self.base
        self.pr['head']['sha']=git(self.repo,'rev-parse','refs/heads/feature')
        if '/git/commits/' in path:
            sha=path.rsplit('/',1)[1]
            return {'sha':sha,'message':git(self.repo,'show','-s','--format=%B',sha),
                    'parents':[{'sha':p} for p in git(self.repo,'show','-s','--format=%P',sha).split()],
                    'tree':{'sha':git(self.repo,'rev-parse',sha+'^{tree}')},
                    'author':{'email':git(self.repo,'show','-s','--format=%ae',sha)}}
        if path.endswith('/git/blobs'):
            return {'sha':self.execute('hash-object','-w','--stdin',input=base64.b64decode(data['content']))}
        if path.endswith('/git/trees'):
            with tempfile.TemporaryDirectory() as tmp:
                env=os.environ|{'GIT_INDEX_FILE':str(Path(tmp)/'index')}
                self.execute('read-tree',data['base_tree'],env=env)
                for entry in data['tree']:
                    if entry['sha'] is None: self.execute('update-index','--force-remove',entry['path'],env=env)
                    else: self.execute('update-index','--add','--cacheinfo',entry['mode']+','+entry['sha']+','+entry['path'],env=env)
                return {'sha':self.execute('write-tree',env=env)}
        if path.endswith('/git/commits'):
            env=os.environ.copy()
            for role in ('AUTHOR','COMMITTER'):
                identity=data[role.lower()]
                env.update({f'GIT_{role}_NAME':identity['name'],f'GIT_{role}_EMAIL':identity['email'],f'GIT_{role}_DATE':identity['date']})
            sha=self.execute('commit-tree',data['tree'],'-p',data['parents'][0],input=data['message'].encode(),env=env)
            self.created_commits+=1
            return {'sha':sha}
        if '/git/refs/heads/' in path:
            self.execute('update-ref','refs/heads/feature',data['sha'],self.pr['head']['sha'])
            self.pushes+=1
            return {'object':{'sha':data['sha']}}
        return super().__call__(method,path,data)


class AcceptanceTests(unittest.TestCase):
    def assert_tests_pass(self,workspace):
        result=subprocess.run(['python3','-B','-m','unittest','discover','-s','tests'],cwd=workspace/'source',capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        return True

    def test_install_review_repair_and_replay_both_modes(self):
        reports=[]
        for mode in ('self_hosted','api'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp); repo=root/'project'
                shutil.copytree(ROOT/'examples/python-project',repo)
                init_repo(repo)
                fixture=root/'fixture'; fixture.mkdir()
                unused,fixture_cfg,_=test_codex.CodexTests().runtime_fixture(fixture)
                cfg=sample_config(mode)|{'auto_fix':True,'allowed_actors':['owner'],'entry_isolation':{'status':'verified'},
                                         'isolation':fixture_cfg['isolation']}
                if mode=='api': cfg['api_budget']={'approved_usd':5,'max_calls':20}
                cfg=validate_config(cfg)
                isolation=Path(cfg['isolation']['report_path'])
                isolation.write_text(json.dumps(json.loads(isolation.read_text())|{'mode':mode}))
                config_path=root/'config.json'; config_path.write_text(json.dumps(cfg))
                installed=subprocess.run(['python3',str(ROOT/'runtime/reviewctl.py'),'install','--target',str(repo),
                                           '--config',str(config_path),'--apply'],capture_output=True,text=True)
                self.assertEqual(installed.returncode,0,installed.stderr)
                with (repo/'REVIEW.md').open('a') as handle: handle.write('\nPreserve the project-specific duplicate item rule.\n')
                base=commit_files(repo,{'README.md':'Every item counts; equal amounts remain separate line items.\n'})
                git(repo,'checkout','-b','feature')
                head=commit_files(repo,{'src/total.py':'def total_cents(items: list[int]) -> int:\n    return sum(set(items))\n'})
                transport=GitTransport(repo,base); api=GitHub('fixture-only',transport)
                current=api.call('GET','/repos/example/project/pulls/1')
                workspace=root/'bug-input'; manifest=prepare_workspace(repo,base,head,workspace,[])
                run=sample_run()|{'mode':mode,'auth_kind':'chatgpt' if mode=='self_hosted' else 'api_key',
                                  'base_sha':base,'head_sha':head,'policy_sha':base,'input_digest':input_digest(current),
                                  'config_digest':digest(cfg),'rules':{'REVIEW.md':manifest['rules']['REVIEW.md']},
                                  'created_at':'2026-11-16T00:00:00Z','intent':{'title':current['title'],'body':current['body']},
                                  'changed_paths':manifest['changed_paths']}
                state=initial_state(run,cfg)
                # Existing distinct-item test passes despite the duplicate-item bug.
                state=inspect_state(state,cfg,{'status':'passed','head_sha':head} if self.assert_tests_pass(workspace) else None,api)
                issue=finding()|{'line':2}
                def model(value):
                    request=build_request(state['next_role'],state,workspace,cfg)
                    if mode=='api': return normalize_action(json.dumps(value),'success')
                    executable=root/'fake-codex'
                    executable.write_text(FAKE_CODEX_HEADER + 'print('+repr(test_codex.events(value))+')\n'); executable.chmod(0o755)
                    return run_codex(request,executable,request['timeout_s'])
                outcomes={mode:'success',('api' if mode=='self_hosted' else 'self_hosted'):'skipped'}
                for value in (output([issue]),output(),output([issue])|{'dispositions':[{'id':issue['id'],'decision':'confirmed','reason':'set removes distinct line items'}]}):
                    state=collect_state(state,cfg,outcomes,model(value),api,repo)
                self.assertEqual(state['next_role'],'fix')
                old_stages={h['role']:h['result'] for h in state['history']}
                candidate=root/'bug-candidate'; bug_case=propose_case(state,workspace,candidate)
                fix='diff --git a/src/total.py b/src/total.py\n--- a/src/total.py\n+++ b/src/total.py\n@@ -1,2 +1,2 @@\n def total_cents(items: list[int]) -> int:\n-    return sum(set(items))\n+    return sum(items)\n'
                regression='import unittest\nfrom src.total import total_cents\n\nclass DuplicateTests(unittest.TestCase):\n    def test_duplicates(self):\n        self.assertEqual(total_cents([100, 100]), 200)\n'
                lines=regression.splitlines()
                fix+='diff --git a/tests/test_duplicates.py b/tests/test_duplicates.py\nnew file mode 100644\n--- /dev/null\n+++ b/tests/test_duplicates.py\n@@ -0,0 +1,'+str(len(lines))+' @@\n'+''.join('+'+line+'\n' for line in lines)
                fix_state=copy.deepcopy(state)
                state=collect_state(state,cfg,outcomes,model(output()|{'patch':fix}),api,repo)
                self.assertEqual(state['phase'],'tests')
                self.assertNotEqual(state['head_sha'],head)
                retry=publish_patch(fix_state,fix,cfg,repo,api)
                self.assertEqual(retry['head_sha'],state['head_sha'])
                self.assertEqual((transport.created_commits,transport.pushes),(1,1))
                workspace=root/'fixed-input'; prepare_workspace(repo,base,state['head_sha'],workspace,[])
                state=inspect_state(state,cfg,{'status':'passed','head_sha':state['head_sha']} if self.assert_tests_pass(workspace) else None,api)
                self.assertFalse(state['terminal'])
                for value in (output(),output(),output()|{'dispositions':[{'id':issue['id'],'decision':'resolved','reason':'sum retains duplicates and regression passes'}]}):
                    state=collect_state(state,cfg,outcomes,model(value),api,repo)
                self.assertEqual(state['status'],'verified')
                self.assertEqual(state['head_sha'],state['tested_head'])
                for _ in range(2): publish_result(state,cfg,api,api)
                self.assertEqual(len(transport.comments),1)
                self.assertEqual(len(transport.checks),3)
                self.assertTrue(all(c['head_sha']==state['head_sha'] for c in transport.checks))
                self.assertEqual(next(c for c in transport.checks if c['name']=='review-guide/ci')['conclusion'],'success')
                clean_candidate=root/'clean-candidate'; clean_case=propose_case(state,workspace,clean_candidate)
                cases=[]
                for name,origin,record,answers in (('bug',candidate,bug_case,[issue]),('clean',clean_candidate,clean_case,[])):
                    decision=OperatorDecision('fixture operator','2026-11-16T00:00:00Z',record['input_digest'],'synthetic test only',answers,bool(answers),'holdout')
                    with patch.dict(os.environ, {'GITHUB_ACTIONS': 'false', 'REVIEW_WORKER': ''}):
                        cases.append(confirm_case(origin,decision,root/name))
                    materialize_case(root/name,root/(name+'-worker'))
                configs=[cfg|{'model':m,'tools_digest':digest('fixture tools'),'rules_digest':digest('fixture rules')} for m in ('fixture-incumbent','fixture-candidate')]
                rubric={'version':1,'critical_trials':3}
                evaluation=build_eval_manifest(cases,configs,rubric)
                rows=[[],[]]
                for trial in evaluation['expected']:
                    bug=trial['case_id']==bug_case['id']; case_record=cases[0] if bug else cases[1]
                    stages=old_stages if bug else {r:output() for r in ('bugs','security','verify')}
                    record=trial|{'corpus_digest':evaluation['corpus_digest'],'rubric_digest':digest(rubric),
                                  'input_digest':case_record['input_digest'],'status':'complete','stages':stages,
                                  'tools_digest':digest('fixture tools'),'rules_digest':digest('fixture rules'),'usage':None,'elapsed_s':1}
                    matches={issue['id']:issue['id']} if bug else {}
                    judgment={'actor':'fixture operator','at':'2026-11-16T00:00:00Z','reason':'synthetic semantics',
                              'matches':{'bugs':matches,'security':{},'verify':matches},'extras':{}}
                    rows[0 if trial['configuration_digest']==digest(configs[0]) else 1].append(JudgedTrial(copy.deepcopy(record),copy.deepcopy(judgment)))
                report=compare_runs(evaluation,*rows,rubric)
                self.assertEqual(report['decision'],'eligible_for_human_review')
                bad=next(row for row in rows[1] if row.record['case_id']==bug_case['id'])
                bad.record['stages']['verify']=output(); bad.judgment['matches']['verify']={}
                self.assertEqual(compare_runs(evaluation,*rows,rubric)['decision'],'hold')
                self.assertIn('project-specific',(workspace/'policy/REVIEW.md').read_text())
                reports.append((state['status'],report['expected_count']))
        self.assertEqual(reports,[('verified',8),('verified',8)])

    def test_sensitive_auth_change_requires_human_even_if_model_calls_it_low(self):
        cfg=sample_config()|{'auto_fix':True}
        self.assertEqual(classify_risk(['auth/access.py'],'low',cfg)['risk'],'high')
        from tests.git_fixture import patch_file
        self.assertEqual(check_patch(patch_file('auth/access.py'),sample_run()|{'fix_paths':['auth/access.py']},cfg,None)['status'],'needs_human')

    def test_failed_model_and_stale_input_never_reach_patch_publication(self):
        from runtime.review_guide.codex import normalize_result
        for mode in ('self_hosted','api'):
            cfg=sample_config(mode)|{'auto_fix':True}
            if mode=='api':cfg['api_budget']={'approved_usd':5,'max_calls':3}
            transport=test_github.Fake(); api=GitHub('fixture',transport)
            state=initial_state(sample_run()|{'mode':mode,'auth_kind':'chatgpt' if mode=='self_hosted' else 'api_key',
                                            'input_digest':input_digest(transport.pr)},cfg)
            failures=[normalize_result('',None,True), normalize_result('{"type":"error","message":"auth expired"}',1,False),
                      normalize_result('{"type":"turn.failed","error":{"message":"quota"}}',0,False)]
            for failure in failures:
                result=collect_state(state,cfg,{mode:'success'},failure,api,Path('/never-used'))
                self.assertTrue(result['terminal'])
                self.assertIn(result['status'],{'failed','incomplete'})
                self.assertIsNone(result['next_role'])
            transport.pr['head']['sha']='0'*40
            result=collect_state(state,cfg,{mode:'success'},output(),api,Path('/never-used'))
            self.assertEqual(result['reason'],'stale_head')
            self.assertTrue(all(method=='GET' for method,_,_ in transport.requests))
