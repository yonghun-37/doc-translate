# doc-translate 개발 지침

- 문서와 UI 문구는 한국어로 씁니다. 코드 식별자·주석은 영어로 써도 됩니다.
- 구현 기준은 `docs/specs/job-model.md`와 `docs/specs/design.md`입니다. 작업·입력·상태 규칙은 job-model.md가 우선합니다. 명세와 다르게 구현해야 하면 명세를 고치고 이유를 `docs/PROJECT_STATE.md`에 남깁니다.
- 현재 진행 상황·알려진 한계·다음 할 일은 `docs/PROJECT_STATE.md`에 유지합니다.
- Python 3.12, `uv` 사용. 가상환경은 `.venv/`(필요 패키지 설치됨). 테스트: `.venv/bin/python -m pytest -q`.
- 처음부터 만들지 않습니다. 추출·되쓰기·LLM 호출은 docutranslate, docx 비교는 python-redlines, xlsx 비교는 daff를 씁니다. 라이브러리 소스를 복사·수정하지 말고 래퍼·서브클래스로 확장합니다.
- 출력 파일은 docutranslate가 만듭니다. 직접 보완하는 부분(xlsx 머리글·바닥글)은 zip의 해당 XML 파트만 교체합니다. openpyxl로 출력 파일을 저장하지 않습니다.
- `jobs/<job_id>/inputs/`의 모든 입력 파일은 등록 후 불변입니다. 파일을 고치려면 새 작업으로 올립니다. 작업 삭제는 inputs를 포함한 작업 폴더 전체를 삭제합니다.
- 테스트는 네트워크 없이 돌아야 합니다. 실제 번역 API를 호출하지 않습니다.
- 데이터 폴더(`jobs/ logs/`)의 내용물은 git에 넣지 않습니다(`.gitkeep`만).
- 실제 LLM 호출은 웹의 [번역 실행]·[재시도] 또는 `doc-translate check-translator`를 사용자가 명시적으로 실행할 때만 합니다.
