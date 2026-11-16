# 평가 입력 예시

`rubric.json`은 기본 평가 규칙이다. `judgment.json`은 **승인되지 않은 빈 양식**이다.
`matches`는 역할별 `{실제_지적_ID: 기대_정답_ID}`이며 문구 일치가 아니라 조건·위치·영향을 사람이 확인해 연결한다.
`extras`는 `역할:지적_ID`를 `false_positive`, `unexpected_true_positive`, `pending`으로 분류한다. 분류가 빠진 새 지적은 pending이다.

실제 사례는 프로젝트 `.review/evals/cases/<case-id>/`에 둔다. 이 예시 폴더에는 실제 사람이 확정한 사고 사례가 없다.
초기 정상/버그 Python 사례는 [인수용 샘플](../python-project/)에서 후보를 생성한 뒤 확인한다.
