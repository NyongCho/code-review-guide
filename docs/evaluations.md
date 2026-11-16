# 리뷰 경험과 모델 교체 평가

프로젝트가 사례와 판정 기준을 소유한다. 원본 guide를 계속 실행할 필요가 없다. 리뷰 댓글, 수정 성공, 테스트 통과는 정답의 증명이 아니므로 먼저 candidate로 저장한다. 워크플로는 수정 직전과 검증 완료 시점의 artifact에 후보를 함께 저장한다. 원본 artifact 기본 보존 기간은 14일이다. 장기 보존할 사례는 그 전에 운영자 환경으로 가져온다.

## 후보와 정답 확정

실패가 있던 **당시 head**의 `state.json`과 `workspace/`를 같은 artifact에서 가져온다. 수정된 head의 소스와 과거 지적을 섞으면 안 된다.

```bash
python3 .review/bin/reviewctl.py case propose \
  --run evidence/state.json --snapshot evidence/workspace \
  --output .review/evals/candidates/example
python3 .review/bin/reviewctl.py case confirm \
  --candidate .review/evals/candidates/example \
  --answers answers.json --reason '입력 조건과 영향, 코드 근거를 직접 확인함' \
  --critical --split holdout --output .review/evals/cases/CASE_ID
```

`answers.json`은 model-output schema의 finding 객체 배열이다. 정상 사례는 빈 배열이다. CLI는 확인 내용을 표시하고 입력 digest 전체를 직접 입력하게 한다. TTY 없는 CI/worker에서는 확정할 수 없다. P0/P1 정답은 자동으로 중요 사례가 된다. 실제 case.json의 `id`를 폴더명으로 사용한다.

확정 명령은 worker가 접근할 수 없는 운영자 계정/컴퓨터에서 수행한다. TTY나 actor 문자열만으로 사람 신원을 증명하는 설계가 아니다. OS 접근 경계가 전제다. AI가 만든 승인 JSON은 `confirm_case`의 승인 객체로 받아들이지 않는다.

## 문제집과 실행 조건 고정

문제 입력은 소스·diff·당시 규칙·프롬프트·schema·의도다. case.json의 정답·출처·이전 리뷰 기록, 운영 설정, Git 이력은 reviewer 작업 공간에 복사하지 않는다. `materialize`만으로 격리를 검증했다고 보지 않는다. [런타임 격리](decisions/runtime-isolation.md)를 실제 worker에서 통과해야 한다. 상위 정답 폴더/다른 실행 자료 읽기, 셸 네트워크, 웹 검색, MCP 및 원본 PR 조회를 모두 막는다.

```bash
python3 .review/bin/reviewctl.py eval conditions \
  --profile /PATH/TO/DEDICATED_CODEX_HOME/config.toml --output tools.json
```

`tools.json`의 tools_digest를 incumbent.json, candidate.json 두 실행 설정에 넣는다. 나머지는 프로젝트 config와 같은 형식이며 비교하려는 model/effort/codex_version만 바꾼다. 프로필은 도구·네트워크·지침 발견 조건을 나타내며 실제 호출 직전에 다시 대조한다. API와 구독 모드는 별도 평가한다. 서로 다른 도구 정책을 같은 조건의 모델 비교라고 보고하지 않는다.

```bash
python3 .review/bin/reviewctl.py eval prepare \
  --cases .review/evals/cases/CASE_A .review/evals/cases/CASE_B \
  --configurations incumbent.json candidate.json \
  --rubric rubric.json --output .review/evals/manifest.json
```

rules_digest는 입력에 포함된 실제 정책 파일에서 계산한다. manifest에는 corpus/rubric/config digest와 기대 `(case_id, configuration_digest, trial_index)` 전체 목록이 고정된다. 중요 사례는 최소 3회, 나머지는 1회다. 튜닝 사례와 holdout을 섞지 않는다. holdout 결과로 프롬프트를 조정했다면 그 사례는 다음 평가에서 독립 holdout으로 취급하지 않는다.

## 실행과 사람이 확인한 채점

구독 방식 로컬 실행은 다음과 같다. workspace는 검증한 permission profile이 허용하는 새 입력 폴더여야 한다.

```bash
python3 .review/bin/reviewctl.py eval run \
  --manifest .review/evals/manifest.json --case .review/evals/cases/CASE_A \
  --configuration CONFIGURATION_DIGEST --trial 1 \
  --workspace /PATH/TO/ISOLATED_INPUT --executable /PATH/TO/PINNED_CODEX \
  --output trial-1.json
```

GitHub에서는 설치된 **Evaluate one frozen trial** workflow를 protected branch에서 실행한다. manifest는 `.review/evals/`에 대한 상대 경로다. case_id/configuration/trial은 고정 목록의 값을 사용한다. 선택한 mode의 worker만 실행하며 bugs/security/verify 각각 새 세션을 쓴다. API 경로는 공식 Codex Action을 사용하고, 평가 job에는 게시/수정 권한이 없다. 실패한 trial을 목록에서 삭제하거나 다른 인증으로 바꾸지 않는다. 전체 기대 목록을 실행한 뒤 결과를 비교한다.

[판정 양식](../examples/eval-cases/judgment.json)의 matches/extras를 실제 결과와 정답을 보고 채운다. 별도 AI judge는 v1에서 활성화하지 않는다. 먼저 고정 judge/version과 사람이 확인한 calibration 사례가 필요하다.

```bash
python3 .review/bin/reviewctl.py eval judge \
  --record trial-1.json --judgment judgment-1.json --output judged-1.json
python3 .review/bin/reviewctl.py eval compare \
  --manifest .review/evals/manifest.json --rubric rubric.json \
  --baseline old-1.json old-2.json old-3.json old-4.json \
  --candidate new-1.json new-2.json new-3.json new-4.json --output comparison.json
```

judge 명령 역시 운영자 TTY 확인을 요구한다. 확인한 실행+판정 전체를 운영자 전용 0600 key로 서명한다. 기본 key는 `~/.config/review-guide/operator.key`이며 worker/저장소/artifact에 넣지 않는다. 서명은 판정의 정확성을 보장하지 않으며, worker가 actor 필드만 위조한 파일을 비교에 끼워 넣는 것을 방지한다. key를 잃으면 이전 판정을 재확인하거나 안전하게 보관한 key를 복구해야 한다.

비교 결과는 탐지, verifier 유지, 최종 지적, 중요/일반 누락, 오탐/보류, 완료율, 시간, 관측 사용량을 분리한다. v1 최종 지적은 verifier 결과다. 누락·중복·알 수 없는 trial·입력/도구/규칙/rubric 불일치·미완료·보류는 전체 hold다. 중요 누락 하나, 기존 대비 탐지/최종 결과 감소, 최종 오탐 증가도 hold다. 사용량이 없으면 unknown이며 0으로 채우지 않는다.

통과해도 `eligible_for_human_review`까지다. 사람이 비교 결과와 비용/격리 증거를 확인한 후 별도 설정 변경으로 승격한다. 정상/버그 한 쌍과 몇 번의 실행은 광범위한 모델 동등성의 증거가 아니다. maintain 스킬은 반복 지적을 회귀 테스트/린트, 규칙 변경안, 사례 후보로 제안하고 승인 전에 정책이나 정답을 바꾸지 않는다.
