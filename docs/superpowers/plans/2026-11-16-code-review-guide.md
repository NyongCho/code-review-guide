# Code Review Guide Implementation Plan

> 독립 구현 검토 보완: 필수 검사는 별도 게시 App에 묶고 strict 최신 branch를 요구한다. 승인할 변경 의도는 head commit 메시지로 고정하며 가변 PR 제목/본문은 승인 입력에서 제외한다. 근거와 테스트는 [구현 검토 기록](../reviews/2026-11-16-code-review.md)에 남긴다.

> 구현 중 승인된 변경(2026-11-16): 사용자가 private 보호 기능의 Pro 제한 대신 공개 샘플 테스트를 선택했다. API만 public same-repo/허용 작성자로 확장하고 구독은 private를 유지한다. 서버 연결은 인증된 Actions runner 대신 보호 환경의 제한된 SSH worker로 구현한다. 아래 초기 설계/계획은 이 변경과 함께 읽으며 최신 증거는 [검증 상태](../../validation.md)를 따른다.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 프로젝트에 독립적으로 설치되고 경험을 축적하는 AI 리뷰 체계를 만들며, private Python 샘플의 실제 PR에서 self-hosted 구독 방식과 GitHub-hosted API 방식을 각각 검증한다.

**Architecture:** 구축·점검 스킬이 프로젝트를 조사하고, 템플릿과 작은 Python 실행 도구를 프로젝트 안에 설치한다. 두 실행 방식은 동일한 정책·입출력·평가 계약을 사용하며 모델 호출 단계에서만 갈라진다. GitHub Actions가 역할별 모델 호출, 자격증명 없는 테스트, 제한된 게시 작업을 분리하고, 프로젝트가 승인한 사례를 별도의 평가 도구로 재실행한다.

**Tech Stack:** Python 3.11 이상과 표준 라이브러리, unittest, Git, GitHub Actions, 버전을 고정한 Codex CLI 및 공식 openai/codex-action. 실행 도구에 웹 서버·DB·모델 공급자 SDK를 추가하지 않는다.

**Spec:** [승인된 설계](../specs/2026-11-16-code-review-guide-design.md)

## Global Constraints

- 이 가이드 저장소는 public으로 운영한다. 초기 자동 리뷰 실행 대상은 사용자가 관리하는 private 저장소다.
- 이번 사용자의 우선 검증 경로는 self-hosted 방식이다. API 방식도 실제 사용 가능한 workflow·설정·운영 문서·검증 범위에 포함한다.
- 실행 환경으로 Hermes를 요구하지 않는다.
- 초기 AI 리뷰는 관찰 모드로 운영한다. 테스트·린트 등 필수 검사는 차단 조건으로 두며, AI 지적의 차단 전환은 평가 근거와 사용자 승인으로 결정한다.
- 자동 머지는 기본적으로 하지 않는다.
- 운영 정책과 실행 도구는 신뢰된 버전에서 읽는다.
- 정답·수정본·채점용 자료는 리뷰어에게 제공하는 입력과 물리적으로 분리한다.
- 구독 한도 소진 시 유료 API 키로 자동 전환하지 않으며, API 실행 실패 시에도 구독 경로나 다른 공급자로 자동 우회하지 않는다.
- 모델의 가중치를 자동 학습시키는 기능은 첫 범위에 없다.
- 설계의 초기 제안값을 기본 설정으로 채택한다: 리뷰·수정·재검증 최대 3라운드, 중요 사례당 3회 비교.

## Review Focus

- 사용자가 수정한 AGENTS.md와 규칙에 새 템플릿을 재적용해도 편집이 사라지지 않아야 한다. Task 2의 재설치·충돌 테스트로 고정한다.
- PR의 파일명·심볼릭 링크·설정·지시문이 작업 공간이나 정책 경계를 벗어나게 해서는 안 된다. Task 3의 경로·정책 조작 테스트로 고정한다.
- 중복 이벤트, 봇 수정, 사용자의 동시 푸시가 겹쳐도 오래된 결과를 최신 head의 성공으로 게시하지 않아야 한다. Task 6의 경합 테스트로 고정한다.
- 모델의 정상 종료라도 JSON 불완전·인증 오류·사용량 누락을 깨끗한 리뷰로 오인하지 않아야 한다. Task 4의 결과 파서 테스트로 고정한다.
- 문제집의 정답이 검색이나 Git 이력으로 보이거나 검증 에이전트가 중요한 발견을 제거하면 모델 교체가 잘못 승인될 수 있다. Task 7의 격리·최종 결과 회귀 테스트로 고정한다.

---

## 현재 기준과 구현 결정

- 현재 작업 공간에는 설계 문서만 있고 Git 저장소도 아직 없다. 첫 구현 작업에서 Git을 초기화한다. 원격 public 저장소 게시와 private 샘플 생성은 로컬 구현과 구분한다.
- 서버의 기존 Codex 0.118.0은 교체되지 않았다. 임시 0.169.0 + ChatGPT 인증의 단일 응답만 성공했다. runner, 격리, 리뷰·수정, API 호출은 아직 미검증이다. 이 확인을 반복하기 위해 큰 실행 파일을 다시 복사하지 않는다.
- Python 실행 도구는 `runtime/reviewctl.py`와 `runtime/review_guide/`에 둔다. 프로젝트에 설치할 때 `.review/bin/` 아래로 복사하여 원본 checkout 없이 실행한다.
- 설정·결과·평가 manifest는 JSON을 사용한다. Python의 명시적인 검증 함수와 문서화된 schema를 함께 두며 범용 schema 엔진을 새로 만들지 않는다.
- 초기 기본값: 단계별 모델 호출 600초, 첫 trusted entry 시작부터 작업 허용 시간 60분, 원본 artifact 보존 14일, PR별 활성 실행 1개. entry 이후 queue 시간도 포함한 공통 `deadline_at`을 기록한다. 각 단계는 남은 시간으로 timeout을 줄이고 만료 후 새 호출·push를 금지한다. GitHub job timeout을 workflow 전체 제한으로 오인하지 않으며, 최종 상태 게시·정리는 예산 만료 후에도 허용한다. 모델·추론 강도·API 예산은 설치 입력이다. 존재하지 않는 토큰 상한이나 정확한 비용을 보장하지 않는다.
- API 호출 전 프로젝트 선택·키 등록·예산 입력이 필요하다. 예산은 승인된 실행 횟수 제한과 관측 사용량을 포함하며, 공급자 측 비용 제한의 실제 강제 여부를 별도로 표시한다.
- workflow는 설치 시 `max_rounds`에 맞춰 유한한 작업 그래프를 생성한다. 최대 라운드를 바꾸면 workflow도 함께 갱신한다. 무제한 재귀 dispatch나 별도 상주 서비스를 만들지 않는다.
- 한 라운드는 리뷰·보안 검토·지적 검증 → 허용된 수정 생성 → 패치 확인·반영 → 최신 커밋 테스트·재리뷰다. 더 필요한 경우에만 다음 라운드로 진행한다. 마지막 라운드도 최종 테스트와 재리뷰를 생략하지 않는다.
- 같은 workflow 안에서 수정 후 검사를 명시적으로 연결한다. `GITHUB_TOKEN`으로 푸시한 후 새 이벤트가 자동으로 실행될 것을 전제하지 않는다. 실제 head SHA에 필수 검사 결과를 게시한다.
- 자격증명 격리는 모든 PR 입력 기반 모델 실행의 시작 조건이다. 리뷰·보안 검토·verifier도 예외가 아니다. 지원되는 구성으로 실제 격리를 입증하지 못하면 계층 상태 `needs_verification`을 남기고 무자격증명 오프라인 검사만 허용한다. 해당 경로의 실사용 완료를 선언하지 않는다.

## 파일 구성과 설치 결과

| 경로 | 책임 |
| --- | --- |
| `skills/review-bootstrap/SKILL.md`, `skills/review-maintain/SKILL.md` | 초기 조사·적용·인수, 사건/배포/모델 변경 시 점검 |
| `templates/project/` | REVIEW.md, 프로젝트별 점검 스킬, 정책·계층별 상태·PR 양식·평가 디렉터리 |
| `templates/workflows/` | 두 실행 모드와 공통 테스트·게시 단계의 생성용 workflow 템플릿 |
| `runtime/reviewctl.py`, `runtime/review_guide/` | 설치, 계약 검증, 정책, 호출 입출력, 상태 전이, GitHub 연동, 평가 |
| `schemas/` | 설정·모델 출력·실행 기록·평가 사례의 JSON schema |
| `tests/`, `tests/fixtures/` | 외부 호출 없는 동작 테스트, 모델·GitHub 응답과 Git 저장소 fixture |
| `examples/python-project/`, `examples/eval-cases/` | 비밀·개인 자료 없는 정상/버그/민감 변경 합성 예제 |
| `docs/setup-self-hosted.md`, `docs/setup-api.md`, `docs/operations.md` | 설치·격리·권한·장애·업데이트 안내 |
| `docs/evaluations.md`, `docs/validation.md`, `README.md` | 문제집 운영, 검증 증거, 시작 방법과 지원 범위 |

설치 대상에는 `.review/config.json`, `.review/manifest.json`, `.review/layers.json`, `.review/bin/`, `.review/prompts/`, `.review/schemas/`, `.review/evals/{candidates,cases}/`, `REVIEW.md`, `.agents/skills/review-maintain/SKILL.md`, `.github/workflows/review-*.yml`을 둔다. 모든 schema·프롬프트의 위치와 hash를 manifest에 넣는다. `AGENTS.md`와 PR 템플릿에는 관리 블록만 추가한다. 기존 동명 파일은 덮어쓰지 않고 병합안을 만든다. 원본 로그는 Git 추적 대상에서 제외하고 승인된 사례만 커밋한다.

공통 Python 표기: `Json = dict[str, Any]`, 파일 경로는 `pathlib.Path`. 아래 함수는 CLI와 테스트가 공유하는 내부 인터페이스이며 별도 서비스 API가 아니다.

## 이벤트·권한·신뢰된 실행 경로

| 진입점 | workflow/ref와 actor | 실행 위치·권한 |
| --- | --- | --- |
| 일반 PR CI | `pull_request`, PR ref; private/same-repo | 인증 없는 일회성 테스트 환경. 모델·게시·dispatch secret 및 인증 runner 접근 없음 |
| 리뷰 자동 진입 | `pull_request_target`의 보호된 default branch workflow; opened/synchronize/reopened/edited, 허용된 base·작성자 확인 | GitHub-hosted 제어 job. PR 스크립트 실행 금지; 자료 조회와 선택 경로 시작만 허용 |
| 리뷰 재실행 | 보호된 default branch의 `workflow_dispatch`; 권한 있는 운영자 | 동일 입력 재조회와 동일 경계 적용. branch ref를 바꾼 dispatch 거부 |
| 민감 변경 승인 | 별도의 `review-approve.yml`을 보호된 default branch에서 `workflow_dispatch`; 권한 확인된 사람 | 모델 worker 없이 승인 원본 run/event를 검증. target input/patch digest와 연결 |
| 모델 worker | 위 진입점에서 호출한 고정 workflow/ref; actor와 최초 요청을 계속 기록 | self-hosted 전용 runner 또는 GitHub-hosted API worker. 조회 자료를 준비한 뒤 모델에는 게시/dispatch 권한을 전달하지 않음 |
| 결과·패치 게시 | 신뢰된 job, 확인한 worker artifact와 필요한 승인 원본만 입력 | publisher 전용 token으로만 writes. PR/worker 코드를 실행하지 않음 |

v1 기본 대상 base는 보호된 default branch다. self-hosted는 runner group의 **repository 및 selected workflow/ref 제한이 실제 지원·집행되는 경우**에만 target repo의 worker에 연결한다. 단순 runner label은 접근 통제가 아니다. 계정이 이 제한을 지원하지 않으면 runner를 별도 private 제어 저장소에만 등록한다. 이 경우 target의 보호된 entry는 보호 환경에 보관한 dispatch 전용 GitHub App 자격으로 제어 저장소의 default workflow를 시작하고, 제어 저장소가 target의 PR/입력/권한을 재조회한다. 대상 repo에는 구독 인증과 해당 runner를 연결하지 않는다. 제어 저장소의 운영 workflow와 허용 ref도 보호하고, PR 자체의 workflow가 인증 worker를 시작할 수 없도록 환경·이벤트 정책을 검증한다. 필요한 플랫폼 보호를 구성할 수 없으면 그 경로를 활성화하지 않는다.

API secret 및 dispatch 자격은 보호된 default branch에서만 접근 가능한 GitHub Environment에 둔다. 단순 repository secret 배치는 지원 구성으로 인정하지 않는다. 임의 PR/feature ref가 새 workflow나 job을 추가하여 runner·environment에 접근하는 음성 검사를 설치 인수에 포함한다. 제어 저장소 방식은 배포 선택안이며 이번 문서 수정으로 원격 저장소를 만들거나 플랫폼 기능을 사용 가능하다고 확정한 것이 아니다.

실제 테스트 코드는 token이 없는 별도 실행 경계에서만 실행한다. GitHub job 분리만으로 테스트 프로세스의 credential 접근이 막혔다고 간주하지 않는다. 배포 시 이벤트, workflow SHA/ref, 환경 보호와 runner 접근 정책을 증거로 기록한다.

### Task 1: 실행 계약과 기본 설정

**Files:** Create `runtime/reviewctl.py`, `runtime/review_guide/{__init__,contracts,cli}.py`, `schemas/{config,model-output,run,case,eval-manifest}.schema.json`, `tests/{__init__,test_contracts}.py`, `.gitignore`.

**Interfaces:** Produces `validate_config(value: Json) -> Json`, `validate_output(value: Json, role: str) -> Json`, `validate_run(value: Json) -> Json`, `validate_case(value: Json) -> Json`, `validate_eval_manifest(value: Json) -> Json`, `ValidationError`, `main(argv: list[str] | None = None) -> int`.

- [ ] **1. Git을 초기화하고 계약의 실패 테스트를 작성한다.** 임시 파일만 생성하는 unittest로 다음 assertion을 고정한다. `sample_config()` 등 fixture 팩터리는 이 테스트 파일에서 정의한다.

```python
def test_defaults_and_explicit_mode(self):
    cfg = validate_config(sample_config(mode="self_hosted"))
    self.assertEqual((cfg["max_rounds"], cfg["critical_trials"]), (3, 3))
    self.assertEqual((cfg["review_mode"], cfg["auto_merge"]), ("observe", False))
    with self.assertRaises(ValidationError):
        validate_config(sample_config(mode="automatic_fallback"))
```

- [ ] **2. `python3 -m unittest tests.test_contracts -v`를 실행한다.** 구현 전 import/검증 함수 부재로 실패하는지 확인한다.
- [ ] **3. 계약과 `reviewctl validate --config PATH`를 구현한다.** 설정에는 mode(`self_hosted`/`api`), 버전·모델·명령·경로·상한·관찰/차단 정책·수정 범위·예산 확인을 포함한다. 실행에는 repo/PR/base/head/policy SHA, PR 의도·맥락 snapshot의 `input_digest`, 실제 읽은 규칙 hash, prompt/model/CLI/Action/runner/auth 종류, round/role, `deadline_at`, 검사 증거를 넣는다. 비밀 값은 허용하지 않는다. eval manifest는 corpus/rubric/input hash와 configuration별 case/trial 기대 목록을 갖는다.
- [ ] **4. 출력 검증을 완성한다.** finding은 안정적인 id, 종류(`bug`/`security`/`spec`), 중요도(P0–P3), 상대 경로·위치, 조건·영향·근거를 요구한다. 상태는 `verified`, `findings`, `needs_human`, `incomplete`, `failed`; stale 결과는 `incomplete`와 이유로 표현한다. 필드 누락, 잘못된 상태, 비양수 상한, API 예산 미확인, 근거 없는 finding을 거부하는 테스트를 통과시킨다.
- [ ] **5. 위 테스트와 `python3 runtime/reviewctl.py --help`를 확인하고 관련 파일을 `feat: define review execution contracts`로 커밋한다.**

### Task 2: 독립 설치와 프로젝트별 스킬

**Files:** Create `runtime/review_guide/install.py`, `templates/project/`, `skills/review-bootstrap/SKILL.md`, `skills/review-maintain/SKILL.md`, `tests/test_install.py`, `README.md`.

**Interfaces:** Consumes Task 1 validators. Produces `plan_install(target: Path, bundle: Path, config: Json) -> Json`, `apply_install(target: Path, proposal: Json) -> Json`; CLI `install --target PATH --config PATH --dry-run`와 명시적 `--apply`.

- [ ] **1. 스킬 작성 전에 `skill-creator`, `writing-for-agents`, `superpowers:writing-skills`를 읽고 필요한 검증 절차를 적용한다.** 두 스킬은 조사 → 적용안 → 실행 확인을 안내하며 미검증 상태를 완료로 바꾸지 않는다.
- [ ] **2. 임시 대상 저장소를 사용하는 실패 테스트를 작성한다.** `test_reinstall_preserves_user_edits`는 기존 AGENTS 주변 문구와 REVIEW.md 추가 규칙이 그대로이고 `self.assertEqual(agents.count("<!-- review-guide:start -->"), 1)`임을 검증한다. `test_update_reports_conflict`는 로컬·upstream이 같은 부분을 바꾸면 `self.assertEqual(target.read_text(), edited_text)`이고 충돌안이 생성됨을 검증한다. `test_installed_runtime_is_independent`는 source bundle을 제거한 뒤 설치된 `reviewctl --help`, 요청 구성과 모의 모델 실행을 검사한다. `self.assertTrue(schema_path.is_file())`와 모든 request 참조 경로가 설치 대상 안에 있음을 확인한다. Task 4에서 모델 실행까지 테스트를 확장한다.
- [ ] **3. `python3 -m unittest tests.test_install -v`가 실패함을 확인한다.**
- [ ] **4. 설치 계획·적용과 템플릿을 구현한다.** manifest에 template version, source digest, 설치 당시 기준 사본/hash, 소유 파일을 기록한다. 재적용은 3-way 비교로 변경안을 만들고 충돌을 자동 덮어쓰지 않는다. 생성 중 실패하면 부분 설치를 완료로 기록하지 않는다.
- [ ] **5. bootstrap은 테스트/CI/배포/민감 경로를 조사하고, maintain은 사고·첫 배포·인증 도입·마이그레이션·모델 변경 트리거를 남긴다.** 계층 7개의 상태·증거·적용 조건·다음 작업을 생성한다. 코드 없는 저장소와 1인 승인 한계를 명시한다. `test_empty_project_remains_unverified`에서 모든 계층에 근거 없는 `working`이 없음을 검증한다.
- [ ] **6. 설치 테스트와 스킬 검증을 통과시키고 `feat: install project-owned review guidance`로 커밋한다.**

### Task 3: 신뢰 경계·위험도·수정 허용 범위

**Files:** Create `runtime/review_guide/{policy,workspace}.py`, `tests/{test_policy,test_workspace}.py`, `tests/fixtures/policy/`.

**Interfaces:** Consumes Task 1 config/run. Produces `classify_risk(paths: list[str], ai_risk: str | None, config: Json) -> Json`, `check_patch(patch: str, run: Json, config: Json, approval: Json | None) -> Json`, `prepare_workspace(repo: Path, base: str, head: str, dest: Path, excluded: list[str]) -> Json`.

- [ ] **1. 위험도·패치·스냅샷 실패 테스트를 작성한다.** sensitive path + AI `low`에서 `self.assertEqual(result["risk"], "high")`; 판단 불명에서 `self.assertNotEqual(result["risk"], "low")`를 확인한다. 민감 변경·기존 테스트 삭제/변경·정책 및 평가 정답 변경은 `self.assertEqual(result["status"], "needs_human")`이다. 신규 회귀 테스트는 허용하고, 기존 검사 수정은 보수적으로 사람 확인에 보낸다.
- [ ] **2. 경로 조작 테스트를 추가한다.** `../`, 절대 경로, symlink 탈출, rename으로 민감 경로 숨김, shell 구문이 있는 파일명, PR 안의 완화된 정책과 `AGENTS.override.md`를 입력한다. 밖의 파일이 변경되지 않고 base의 신뢰된 정책이 사용되어야 한다. 민감 승인에서는 repo/base/head/input/policy/patch digest가 다르면 승인 효력이 없어야 한다. 필드가 모두 맞아도 worker가 만든 승인 객체는 Task 6의 권한 경계에서 거절한다.
- [ ] **3. `python3 -m unittest tests.test_policy tests.test_workspace -v`로 실패를 확인한다.**
- [ ] **4. 정책과 스냅샷 생성을 구현한다.** PR 소스는 데이터로만 전달한다. 실행기·정책·프롬프트는 신뢰된 revision에서 로드하고 코드 및 리뷰 맥락 snapshot과 분리한다. CWD와 부모 디렉터리는 trusted 영역에 둔다. PR의 AGENTS 계열, fallback 지침, `.agents/`, `.codex/` 등 고정 CLI가 자동 발견하는 자원은 발견 경로에 두지 않고 원래 경로를 manifest로 매핑한 비활성 데이터로 제공한다. 그 파일 자체의 변경도 리뷰 대상에서 제외하지 않는다. 외부 명령은 인자 배열로 호출한다. 자동 수정은 허용 path와 검증된 지적 범위에만 적용하며 범위를 판정할 수 없으면 사람이 확인한다.
- [ ] **5. 같은 테스트를 통과시키고 `feat: enforce trusted policy and patch boundaries`로 커밋한다.**

### Task 4: 두 모델 실행 경로와 자격증명 격리

**Files:** Create `runtime/review_guide/codex.py`, `templates/project/prompts/{bugs,security,verify,fix}.md`, `templates/workflows/model-worker.yml`, `tests/test_codex.py`, `docs/{setup-self-hosted,setup-api}.md`, `docs/decisions/runtime-isolation.md`.

**Interfaces:** Produces `build_request(role: str, run: Json, workspace: Path, config: Json) -> Json`, `run_codex(request: Json, executable: Path, timeout_s: int) -> Json`, `normalize_result(raw: str, exit_code: int | None, timed_out: bool) -> Json`. Request contains prompt/output/schema paths, argv, role and provenance; secret values are never part of it. API worker passes the same prompt/schema to the official Action and normalizes its output.

- [ ] **1. 모의 실행 파일과 기록된 응답 형식의 fixture로 실패 테스트를 작성한다.** `test_timeout_is_incomplete`는 `self.assertEqual(normalize_result("", None, True)["status"], "incomplete")`, `test_invalid_json_is_failed`는 잘못된 JSON에서 상태 `failed`를 확인한다. `test_missing_turn_completion_is_incomplete`, `test_auth_failure_does_not_fallback`, `test_missing_usage_is_unknown`은 각각 미완료 상태, `self.assertEqual(call_count, 1)`, `self.assertIsNone(result["usage"])`를 확인한다. 성공 프로세스라도 불완전 출력은 성공으로 바꾸지 않는다.
- [ ] **2. `python3 -m unittest tests.test_codex -v`로 실패를 확인한다.**
- [ ] **3. 실행·정규화를 구현한다.** 역할별 새 세션, 명시적인 CLI/model/provider/auth 설정, timeout 시 자식 프로세스 정리, 결과 크기 제한을 적용한다. 개인 메모리·스킬·후크를 가져오지 않는 전용 실행 설정을 사용한다. 지원 플래그를 설치된 CLI `--help`와 smoke로 확인하며 `--ignore-user-config`를 가정하지 않는다. API 키는 Action 입력에만 넣는다.
- [ ] **4. 실제 운영 격리를 별도 probe로 확인하고 결정 문서에 기록한다.** 비밀을 넣기 전 합성 canary로 모델 도구와 프로젝트 테스트 프로세스의 외부 파일·인증 위치·publisher 권한 접근을 검사한다. 지원되는 파일 읽기 제한 permission profile과 실행 계정 경계를 사용하고, API Action은 별도의 `safety-strategy`도 고정한다. legacy sandbox와 permission profile을 혼용하지 않는다. CLI/Action의 지원 여부를 실제 버전에서 확인하며 read-only만으로 격리를 판정하지 않는다. 악성 AGENTS.override/프로젝트 스킬·설정의 자동 로딩도 별도 시작 probe로 검사한다. 격리 실패 시 **모든 PR 입력 기반 모델 호출이 0회**인 `test_isolation_failure_blocks_review_and_fix`를 추가한다. 해결 전에는 무자격증명 오프라인 검사만 허용한다. 실제 secret 값은 출력하지 않는다.
- [ ] **5. 공개 설치 문서를 작성한다.** self-hosted는 Linux 계정·고정 CLI·구독 로그인·private runner·서비스/재시작/동시성·격리 확인, API는 키·모델 접근·사용 예산·고정 Action/CLI·GitHub Secrets를 안내한다. 주소/계정/경로는 placeholder다. Action의 실제 commit SHA와 CLI 버전을 구현 시 공식 소스에서 확인해 고정한다.
- [ ] **6. 테스트를 통과시키고 실제 검증 결과를 경로별로 구분해 `feat: add explicit Codex execution modes`로 커밋한다.** API 키·예산이 없으면 로컬 구현은 검증하되 실제 API probe는 미검증으로 남긴다.

### Task 5: 제한된 리뷰·수정 상태 전이

**Files:** Create `runtime/review_guide/lifecycle.py`, `tests/test_lifecycle.py`, `tests/fixtures/runs/`.

**Interfaces:** Consumes Tasks 1, 3, 4 outputs. Produces `advance(state: Json, event: Json, config: Json) -> Json`, `required_checks(state: Json, config: Json) -> Json`; CLI `advance --state PATH --event PATH --output PATH`. Returned state includes `next_role`, `head_sha`, `round`, terminal status and evidence references.

- [ ] **1. event sequence 기반 실패 테스트를 작성한다.** 정상 리뷰 종료, bug/security의 별도 결과와 verifier, 허용 수정 후 tests+fresh review, 민감 변경 대기, 3라운드 상한, 같은 실패 반복 종료를 검사한다. `test_round_three_still_requires_final_review`는 마지막 수정 후 재리뷰 이전에 `self.assertNotEqual(state["status"], "verified")`, 종료 시 `self.assertLessEqual(state["round"], 3)`을 검증한다.
- [ ] **2. `test_observe_does_not_hide_failure`에서 AI `incomplete`를 보존하되 결정적 CI 상태와 분리함을 확인한다.** `test_blocking_requires_approved_policy`는 승인된 blocking 정책에서 중요 미해결 지적/미완료가 pass가 아님을 확인한다. `test_verified_finding_is_not_closed_without_reason`은 수정·오탐 판단의 근거를 요구한다. fake clock의 `test_deadline_blocks_new_calls_and_pushes`는 queue 시간을 포함한 deadline 이후 새 모델 호출·push 수가 0이고 결과는 `incomplete`임을 확인한다.
- [ ] **3. `python3 -m unittest tests.test_lifecycle -v`로 실패를 확인한다.**
- [ ] **4. 순수 상태 전이와 검사 판정을 구현한다.** 모델이 작업 제어·횟수·머지 여부를 결정하게 하지 않는다. 역할별 결과와 최종 공개 결과를 모두 남기며 미해결 지적은 동일 id로 추적한다. 수정 뒤에는 전체 PR의 새 위험과 기존 지적 해소를 확인하고 초과 범위·반복 실패·한도 소진이면 근거와 함께 종료한다.
- [ ] **5. 상태 전이 테스트를 통과시키고 `feat: coordinate bounded review and repair`로 커밋한다.**

### Task 6: GitHub PR 실행·게시와 최신 커밋 검증

**Files:** Create `runtime/review_guide/{github,workflows}.py`, `templates/workflows/{review-entry,review-round,review-tests,review-publish,review-approve}.yml`, `tests/{test_github,test_workflows}.py`, `.github/workflows/ci.yml`.

**Interfaces:** Produces `render_workflows(config: Json) -> dict[str, str]`, `get_pr(repo: str, number: int, token: str) -> Json`, `resolve_approval(reference: Json, expected: Json, token: str) -> Json`, `publish_result(run: Json, token: str) -> Json`, `publish_patch(run: Json, patch: Path, token: str) -> Json`. GitHub HTTP transport is injectable in tests; credentials are parameters only at the boundary, never serialized. Worker inputs/outputs use Task 1 run contract and Task 5 state. `resolve_approval` re-fetches the original human event and permissions; it never accepts worker-supplied approval claims as authority.

- [ ] **1. fake GitHub transport와 생성 workflow 검증 테스트를 작성한다.** 동일 run key는 같은 댓글/check를 갱신하고 커밋/평가 후보를 중복 생성하지 않는다. 두 번 처리한 뒤 `self.assertEqual(fake.created_comments, 1)`과 `self.assertEqual(fake.created_commits, 1)`을 검증한다. run key는 repo/PR/**base/head/input_digest**/policy/execution-config/round/role의 digest다. 같은 head에서 base나 PR 의도만 바뀌면 key가 달라지는 테스트를 추가한다. 게시·복구 시 입력 전체를 대조하며 head 변경은 `incomplete: stale_head`, base/의도 변경은 `incomplete: stale_input`으로 끝낸다.
- [ ] **2. 중단·경합 테스트를 추가한다.** push 성공 후 응답 유실 시 재조회로 이미 반영된 커밋을 찾아 중복 push하지 않는다. 테스트 실패/취소 시 terminal 성공을 게시하지 않는다. 동일 PR은 concurrency로 직렬화하고 새 사용자 head가 들어오면 오래된 실행을 취소한다. 수정 push는 예상 head를 조건으로 하고 force overwrite하지 않는다.
- [ ] **3. `python3 -m unittest tests.test_github tests.test_workflows -v`로 실패를 확인한다.**
- [ ] **4. 위 이벤트·권한 표에 따른 workflow와 API 경계를 구현한다.** entry는 private/same-repo/허용 작성자와 이벤트를 확인하고 trusted ref의 도구를 사용한다. 보호된 workflow 밖에서 runner·model secret에 접근할 수 없음을 확인한다. 권한이 있는 단계에서는 PR의 스크립트·workflow를 실행하지 않는다. model worker, 자격증명 없는 테스트 환경, publisher를 별도 job/격리 경계로 둔다. artifact는 예상 workflow/run/attempt와 digest를 검증하고 안전하게 추출한다. 민감 승인 resolver는 보호된 approve workflow의 원본 이벤트, 성공 상태, actor/triggering_actor의 사람 여부·현재 권한, 입력·patch digest를 확인한다. 정책 변경은 보호된 ref에서 승인된 변경만 사용한다. `test_worker_cannot_forge_approval`에서 내용·digest가 맞아도 위조한 원본 run/actor는 거절한다.
- [ ] **5. 유한한 라운드 workflow를 생성한다.** 모델 경로별 conditional job에만 runner/auth 차이를 둔다. 합류/finalizer는 dependency의 skip/failure에도 실행될 수 있도록 명시적인 status 조건을 사용한다. 선택한 mode의 성공만 유효 출력으로 받고 반대 경로의 skip은 정상 분기로 처리한다. 취소·실패·출력 누락에서는 후속 모델 호출이나 push를 금지하고 실패 상태만 게시한다. `always()`를 mutation 허가로 사용하지 않는다. 무수정 종료/중간 라운드 종료도 최종 상태 게시로 연결한다. 매 수정 후 실제 새 head를 테스트와 fresh review에 전달하고 publisher가 그 SHA의 필수 검사 결과를 게시한다. 봇 push 후 자동 이벤트에 의존하지 않는다. `test_every_pushed_head_has_explicit_checks` 및 두 mode별 skipped 반대 branch/무수정/중간 종료/실패/취소 시나리오를 검사하며 Task 9에서 실제 DAG로 재확인한다.
- [ ] **6. 최소 GitHub 권한, 14일 artifact 보존, 타임아웃, 기록 복구를 연결한다.** 댓글은 요약과 stable marker만 사용하고 권한 판정의 원장으로 믿지 않는다. 실행 데이터는 검증한 artifact와 GitHub 현재 상태에서 복구한다. 일반 public 가이드 CI는 unittest/문서·workflow 검사만 실행한다.
- [ ] **7. 테스트와 생성 YAML의 actionlint 검사를 통과시키고 `feat: run review loops on GitHub pull requests`로 커밋한다.** actionlint는 개발 검증 도구로 버전을 고정하고 runtime 의존성으로 넣지 않는다.

### Task 7: 경험 수집·문제집·모델 교체 평가

**Files:** Create `runtime/review_guide/{cases,evaluate}.py`, `tests/{test_cases,test_evaluate}.py`, `examples/eval-cases/`, `docs/evaluations.md`.

**Interfaces:** Produces `propose_case(run: Json, snapshot: Path, dest: Path) -> Json`, `confirm_case(candidate: Path, decision: Json, dest: Path) -> Json`, `materialize_case(case: Path, dest: Path) -> Json`, `build_eval_manifest(cases: list[Json], configs: list[Json], rubric: Json) -> Json`, `compare_runs(manifest: Json, baseline: list[Json], candidate: list[Json], rubric: Json) -> Json`. CLI `case propose`, `case confirm`, `eval prepare`, `eval compare` supports these operations; model execution reuses Task 4/6 workers with eval context instead of PR publication.

- [ ] **1. 후보·승인·snapshot 테스트를 작성한다.** 수정 성공/닫힌 댓글은 `candidate`만 만들고 자동 `confirmed`가 되지 않는다. 사람의 decision에는 actor/time/input digest/기대 결과/근거와 승인 출처가 필요하다. v1 case confirm은 모델·worker가 접근할 수 없는 운영자 환경의 명시적 로컬 명령으로만 수행한다. 원본 worker decision을 그대로 confirm 입력으로 채택하지 않는다. 추후 GitHub 승인 연동은 Task 6의 검증된 원본 이벤트만 사용한다. 입력 snapshot이 없거나 source와 hash가 불일치하면 실행하지 않는다. 위조 actor/digest를 넣은 worker 승인 파일의 거절을 테스트한다.
- [ ] **2. 정답 격리와 모델 퇴행 테스트를 작성한다.** materialized workspace에서 answer/fix/rubric과 `.git` 이력을 찾을 수 없어야 한다. 입력에 없는 정답 canary에 대해 `self.assertNotIn(answer_canary, all_readable_text)`를 확인한다. 실제 worker 경계에서는 상위 정답 경로·다른 run 자료·원본 PR로의 도구 접근도 거절돼야 한다. baseline의 중요 발견을 candidate의 verifier가 삭제하거나, 평균이 높아도 중요 누락 1개가 생기면 `self.assertEqual(report["decision"], "hold")`다. 정상 사례의 낯선 발견은 자동 false positive가 아니라 `pending`이다. 기대 trial 하나 삭제/중복/알 수 없는 trial 추가 시 각각 전체 `hold`이고 완료율 분모가 manifest의 기대 수와 같음을 확인한다.
- [ ] **3. `python3 -m unittest tests.test_cases tests.test_evaluate -v`로 실패를 확인한다.**
- [ ] **4. 수집·승인·평가를 구현한다.** answer와 judge 자료는 제어 영역에만 두고 별도 worker 실행 경계에는 input만 전달한다. worker에는 전체 평가 checkout, 다른 실행 artifact, 원본 PR 조회 자격·URL을 주지 않는다. 모델 추론 통신만 허용하고 shell network, 웹 검색, GitHub 연결, MCP는 각각 비활성화해 검증한다. 기대 문제에는 의미상의 조건·위치·영향과 사람 근거를 둔다. 문자열 일치 점수 대신 고정 rubric에 따른 판정을 저장한다. v1 기본 채점은 사람이 확정한 판정이며, AI 보조 채점은 고정 judge/version과 사람이 확인한 calibration 사례가 있을 때만 사용한다.
- [ ] **5. 평가 실행과 보고를 연결한다.** 같은 corpus/hash/rules/tools/rubric에서 중요 사례 3회, 나머지 1회씩 incumbent/candidate를 실행한다. 실행 전 manifest에 `(case_id, configuration_digest, trial_index)` 전체 목록을 고정한다. 탐지·verifier·최종 결과와 중요/일반 누락, 오탐, 보류, 완료율, 시간/관측 사용량을 분리한다. 결과 누락·중복·알 수 없는 trial·조건 불일치·미완료·보류가 있으면 비교 전체를 `hold`로 두며 분모에서 제거하지 않는다. 모두 충족해도 결과는 `eligible_for_human_review`까지이며 자동 모델 변경은 없다.
- [ ] **6. 개선안을 maintain 스킬에 연결한다.** 회귀 테스트/린트, 리뷰 규칙, eval 사례 후보를 근거와 함께 제시하고 사람 승인 전 정책/정답을 바꾸지 않는다. 튜닝/고정 평가 split과 초기 소표본 한계를 문서화한다. 테스트를 통과시키고 `feat: preserve review knowledge through replayable evaluations`로 커밋한다.

### Task 8: 합성 Python 프로젝트와 오프라인 인수 검사

**Files:** Create `examples/python-project/{src,tests}/`, `examples/python-project/README.md`, `tests/test_acceptance.py`, `docs/validation.md`; Modify `README.md`.

**Interfaces:** Consumes Tasks 1–7 CLI and generated files. Produces reusable synthetic fixture snapshots and a per-mode acceptance report; no new runtime interface.

- [ ] **1. 실패 인수 테스트를 작성한다.** 작은 Python 프로젝트에서 금액 합산 시 중복 item을 한 번만 계산하는 버그와, 정상적으로 중복 item을 각각 계산하는 사례를 정의한다. 샘플 함수는 `total_cents(items: list[int]) -> int`이며 기대값은 `self.assertEqual(total_cents([100, 100]), 200)`이다. 기대 동작은 PR 의도에 명시한다. 별도 `auth/` 변경으로 민감 정책을 검사한다. 기존 테스트가 놓친 버그를 리뷰가 잡고 회귀 테스트가 추가되는 흐름을 고정한다.
- [ ] **2. `python3 -m unittest tests.test_acceptance -v`로 실패를 확인한다.**
- [ ] **3. fake model/GitHub 응답을 사용해 설치→리뷰→검증→수정→최신 head 검사→후보 생성→사람 확인→모델 비교를 실행한다.** 두 mode에서 결과 계약·정책·문제집이 같고 설정 변경 시 사용자 규칙이 유지됨을 확인한다. timeout/auth/quota/중복/새 head/중요 회귀도 포함한다.
- [ ] **4. `python3 -m unittest discover -s tests -v`와 actionlint를 실행한다.** 오프라인 테스트가 검증하는 도구 동작과 실제 모델 품질/격리/runner 검증을 결과 문서에서 구분한다.
- [ ] **5. `test: add end-to-end fixture acceptance coverage`로 커밋한다.** 이 단계의 성공만으로 실사용 지원 완료를 선언하지 않는다.

### Task 9: 두 실행 방식의 실제 PR 인수와 운영 인계

**Files:** Modify `docs/{validation,setup-self-hosted,setup-api,evaluations}.md`, `README.md`; Create `docs/operations.md`. Private evidence stays in the private sample repository, public docs contain only redacted summaries.

**Interfaces:** Consumes installed CLI/workflows, synthetic sample, configured runtime. Produces actual PR/head/run/check links and outcome matrix for each mode; all evidence must identify the tested versions.

- [ ] **1. 샘플 소유 계정·이름과 실제 필요한 설정을 먼저 조사한다.** 읽을 수 있는 GitHub/서버 상태는 직접 확인하고 계정 선택·키 등록·API 예산처럼 남은 입력만 요청한다. 사람만 가능한 설정은 `wizard` 스킬 적용 여부를 판단한다. 이미 승인된 검증 경로를 다시 승인받지 않는다. 인증·예산을 기다리는 동안 독립적인 로컬 작업은 완료한다.
- [ ] **2. private Python 샘플과 self-hosted runner를 연결하고 Task 4 격리를 확인한다.** 기본 Codex를 무작정 덮어쓰지 말고 전용 고정 버전을 사용한다. 먼저 계정의 runner/workflow/ref·environment 제한을 확인해 지원 경로를 고른다. PR에 추가한 job뿐 아니라 새 workflow도 인증 runner·secret에 접근하지 못하는 음성 검사를 합성 canary로 수행한다. sample의 필수 CI와 branch protection/ruleset가 실제로 실패를 막는지 확인한다. 계정 플랜으로 불가능하면 제한을 명시하고 완료로 표시하지 않는다.
- [ ] **3. self-hosted 실제 정상/버그/민감 변경 PR을 실행한다.** 올바른 지적과 verifier, 허용 수정, 새 커밋의 테스트·재리뷰, 민감 변경 대기, round cap, 실패·중복·stale 처리를 확인한다. PR 댓글 게시와 수정 커밋은 사용자가 요청한 샘플 검증 범위에 한정한다.
- [ ] **4. 같은 샘플을 명시적으로 API mode로 전환하고 동일한 인수를 수행한다.** 실제 API 키·예산이 준비된 후 호출한다. 모델 접근성이 다르면 모델/실행 조건 차이를 보고한다. 어떤 오류에서도 다른 인증 방식으로 전환하지 않는지 확인한다.
- [ ] **5. 기록에서 사례 후보를 생성하고 사람에게 정답을 확정받아 실제 반복 평가를 수행한다.** 확인되지 않은 사례는 후보로 남긴다. 중요 누락 후보를 거부하는 정책과 동일 corpus 사용을 증거로 남긴다. 정상/버그 한 쌍으로 광범위한 모델 동등성을 주장하지 않는다.
- [ ] **6. 운영 문서를 완성한다.** 재시작·인증 만료·사용 한도·API 예산·중단 복구·로그 보존·업데이트 제안·버전 rollback·첫 배포 준비·사고 기록의 구체적인 명령과 확인 상태를 설명한다. public 문서에서 실제 호스트/키/private 코드/원본 로그를 제외한다.
- [ ] **7. spec §10의 12개 완료 조건을 경로별 증거와 매핑한다.** 모델/도구 테스트, 격리 확인, 실제 PR 실행, 문제집 품질의 결과를 구분한다. 준비되지 않은 항목은 `needs_verification`으로 남기고 README의 지원 범위를 그 결과에 맞춘다.
- [ ] **8. 변경에 필요한 전체 검사를 실행하고 최종 코드 리뷰를 수행한 뒤 `docs: record verified setup and operating procedures`로 커밋한다.** 원격 공개 게시 상태는 별도로 명시한다. 둘 중 하나만 실검증한 경우 두 옵션 모두 완료라고 보고하지 않는다.

## 자기 검토와 설계 대응

| 설계 | 구현 작업 |
| --- | --- |
| §1–4 범위·소유권·초기 적용 | Tasks 1–2, 8–9 |
| §5 7개 계층과 적용 대기 | Task 2 템플릿·스킬, Task 9 인수 |
| §6 위험도·자동 수정·결과 상태 | Tasks 1, 3, 5–6 |
| §7 두 실행 경로와 운영 경계 | Tasks 4, 6, 9 |
| §8 경험과 개선 승인 | Tasks 2, 7 |
| §9 재현·격리·모델 교체 | Task 7, Task 9 실제 비교 |
| §10 샘플 완료 조건 | Tasks 8–9 |
| §11–12 세부 결정과 선행 검증 한계 | 본 계획의 구현 결정, Tasks 4, 9 |

본 계획은 서로 연결되는 설치→실행→평가 흐름 하나를 다룬다. 각 task는 독립적인 테스트/검토 단위이며, 서버 구축과 API 실검증을 제외한 테스트는 비용 없이 로컬에서 실행한다. 공유 함수명·상태·경로를 위 Interfaces와 통일하고 Review Focus 5개를 각 소유 task에 반영했다.

## 구현 시 재확인할 공식 근거

- [Codex GitHub Action](https://learn.chatgpt.com/docs/github-action): 공식 Action 입력과 지원 CLI/sandbox, API 인증 연결. Action commit과 실행 버전은 실제 사용 시 확인한다.
- [Codex 비대화형 실행](https://learn.chatgpt.com/docs/non-interactive-mode): 자동화 인증과 실행 경계. 구독 경로의 private 대상 제한을 유지한다.
- [GitHub workflow 트리거](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow): GITHUB_TOKEN으로 만든 이벤트의 후속 실행 제약 때문에 수정 이후 검사를 명시적으로 연결한다.

상태: 구현 계획 작성 및 자기 검토 완료. 실제 구현·runner 설치·API 호출·샘플 PR 검증은 아직 수행하지 않았다.
