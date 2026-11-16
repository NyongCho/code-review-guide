# Code Review Guide

프로젝트에 맞는 AI 코드 리뷰 체계를 설치하고, 실제 경험을 규칙·검사·평가 문제집으로 축적하는 도구와 스킬이다.

현재 개발 중이다. 로컬 검증 결과와 실제 PR 운영 검증을 구분한다. self-hosted Codex 구독 방식과 GitHub-hosted API 방식을 명시적으로 선택하며 자동 전환하지 않는다.

## 시작

Python 3.11 이상과 Git이 필요하다. 외부 Python runtime 패키지는 필요 없다.

1. `skills/review-bootstrap/SKILL.md`를 구축 에이전트에 제공한다.
2. 프로젝트의 모델·테스트 명령·실행 방식으로 config JSON을 작성한다.
3. 적용안을 확인한 뒤 설치한다.

```bash
python3 runtime/reviewctl.py validate --config project-config.json
python3 runtime/reviewctl.py install --target /path/to/project --config project-config.json --dry-run
python3 runtime/reviewctl.py install --target /path/to/project --config project-config.json --apply
```

설치된 프로젝트는 `.review/bin/reviewctl.py`를 사용한다. 원본 guide checkout을 유지하지 않아도 된다. 재설치는 기존 편집을 보존하고 충돌 시 변경안을 `.review/proposals/`에 남긴다.

## 개발 검증

```bash
python3 -m unittest discover -s tests -v
```

제품 범위와 완료 조건은 [설계](docs/superpowers/specs/2026-11-16-code-review-guide-design.md), 작업 순서는 [개발 계획](docs/superpowers/plans/2026-11-16-code-review-guide.md)에 있다.
