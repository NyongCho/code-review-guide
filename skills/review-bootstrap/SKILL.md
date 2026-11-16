---
name: review-bootstrap
description: Use when initializing or reapplying this guide's AI code review pipeline to a project, including projects without code or deployment yet.
---

# 프로젝트 리뷰 체계 구축

가이드 저장소의 도구를 프로젝트에 독립 설치하고 실제 PR 증거까지 인계한다. 파일 생성과 운영 검증을 구분한다.

1. 대상의 AGENTS.md, 코드, 테스트·CI, 배포, 민감 경로를 조사한다. 제품 의도처럼 자료로 확인할 수 없는 것만 묻는다.
2. 실행 방식을 self_hosted 또는 api로 명시한다. `runtime/reviewctl.py --help`와 선택한 방식의 `docs/setup-*.md`를 확인한다. API는 키를 채팅으로 받지 않고 예산을 명시한다.
3. 프로젝트 설정 JSON과 REVIEW.md 적용안을 만든다. `python3 runtime/reviewctl.py install --target <project> --config <config> --dry-run`으로 충돌을 확인하고 승인된 작업 범위 안에서 `--apply`한다. 기존 지침과 프로젝트에서 발전한 규칙을 보존한다.
4. 설치된 `.review/bin/`, `.review/prompts/`, `.review/schemas/`가 원본 checkout 없이 동작하는지 확인한다. 이후 실행 기준은 대상 프로젝트의 버전이다.
5. 실제 인증을 연결하기 전 격리·workflow 접근 통제를 검증한다. Hello 응답, 파일 존재, AGENTS 링크는 리뷰 체계의 작동 증거가 아니다.
6. 정상·버그 PR에서 리뷰→지적 검증→허용 수정→최신 커밋 테스트·재리뷰→기록을 확인한다. 민감 변경과 정답 확정은 검증된 사람 승인 경로를 사용한다.

인계에는 **7개 계층 각각의 상태·증거·적용 조건·다음 작업**과 실행 방식별 미검증 항목을 포함한다. 계층은 PR 전 검증 / PR AI 리뷰 / 보안 검증 / 필수 CI / 위험도별 사람 확인 / 통합과 점진적 배포 / 감지와 복구다. 정의는 가이드의 `templates/project/.review/layers.json`을 사용하고 설치 대상의 `.review/layers.json`을 채운다. 코드가 없으면 준비 상태로 인계하고 실제 PR 검증 전에는 구축 완료로 표시하지 않는다. 1인 프로젝트의 확인을 독립된 두 사람 승인으로 표현하지 않는다.

원본 리뷰 기록은 후보이며, 자동 수정이나 댓글 종료가 정답을 확정하지 않는다. 실제 경험의 개선안은 프로젝트의 review-maintain 스킬로 연결한다.
