import copy
import json
import tempfile
import unittest
from pathlib import Path
from runtime.review_guide.eval_runtime import trial_request, trial_record, run_trial, describe_tools
from runtime.review_guide.workflows import render_workflows
from tests import test_codex
from tests.fixtures import sample_config, output
from runtime.review_guide.contracts import ValidationError

class EvalRuntimeTests(unittest.TestCase):
    def test_same_workers_use_fresh_roles_and_no_publication(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); workspace,cfg,run=test_codex.CodexTests().runtime_fixture(root)
            run.update(repository='evaluation/input', pr=1, kind='evaluation')
            cfg['tools_digest']=describe_tools(Path(cfg['isolation']['codex_home'])/'config.toml')
            bundle={'run':run,'config':cfg,'trial':{'case_id':'sample'},'stages':{},'requests':{}}
            executable=root/'codex'
            executable.write_text('#!/usr/bin/env python3\nprint('+repr(test_codex.events())+')\n'); executable.chmod(0o755)
            result=run_trial(bundle,workspace,executable)
            self.assertEqual(result['status'],'complete')
            self.assertEqual(set(result['stages']),{'bugs','security','verify'})
            self.assertEqual(len(result['requests']),3)
            self.assertNotIn('source',result)

    def test_failed_stage_prevents_later_calls_and_api_has_no_subscription_fallback(self):
        bundle={'run':{},'config':sample_config('api'),'stages':{'bugs':output()|{'status':'failed'}},'requests':{}}
        with self.assertRaises(ValidationError): trial_request(bundle,'security',Path('/unused'))
        with self.assertRaises(ValidationError): run_trial(bundle,Path('/unused'),Path('/unused'))
        self.assertEqual(trial_record(bundle|{'trial':{}})['status'],'incomplete')

    def test_evaluation_workflow_has_both_modes_and_no_publisher_permissions(self):
        files=render_workflows(sample_config())
        workflow=json.loads(files['.github/workflows/review-evaluate.yml'])
        self.assertEqual(set(workflow['jobs']),{'entry','self_hosted','api'})
        for job in workflow['jobs'].values():
            self.assertNotIn('write',job.get('permissions',{}).values())
        actions=[s for s in workflow['jobs']['api']['steps'] if s.get('uses','').startswith('openai/codex-action@')]
        self.assertEqual(len(actions),3)
