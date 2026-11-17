# 1차 구현 결과

> 이전 구현의 기록입니다. 현재 입력은 [웹 업로드](../web-upload.md)로 전환했으며 감시·신규 자동 번역은 제거했습니다. 최신 상태는 [업로드 구현 결과](../upload-implementation/result.md)를 참고하세요.

기준: [design.md](../design.md), [구현 계획](plan.md). 지정된 라이브러리를 사용하는 1차 기능 구현과 오프라인 검증을 완료했습니다. 커밋·푸시는 하지 않았습니다.

## 구현

- `app/config.py`, `storage.py`, `watcher.py`: 설정·용어집·키 조회/파싱·원격 가드, 원자적 상태, 메타데이터 로그, 파일명/Office ZIP 검증, 안정화 감시.
- `app/reuse_agent.py`, `engine.py`, `xlsx_headers.py`: 정확한 문자열 메모리와 중복 제거, docutranslate 주입, 각주/미주 연결, xlsx headerFooter 보완. 직접 HTTP·배치·재시도 구현 없음.
- `app/diff/`: 공통 JSON, python-redlines Docxodus 변경 추적 문서, daff 시트 HTML, python-pptx 위치별 변경.
- `app/pipeline.py`: 신규 자동 승인, 개정 검토·승인·반려·재시도, 기준본 재검사, 두 언어 성공 후 공개, 원본 불변 및 실패 정리.
- `app/web/`, `cli.py`: 한국어 서버 렌더링 UI·로컬 정적 파일, 문자 강조·백그라운드 번역·내려받기 및 명세의 CLI 명령 전체.
- `pyproject.toml`, `.gitignore`, 데이터 폴더 `.gitkeep`, 용어집·키 없는 설정 예시. 실행에 직접 사용하는 기존 설치 패키지(lxml·MarkupSafe 포함)와 빌드 도구 버전도 고정.

## 검증 결과

최종 실행: `.venv/bin/python -m pytest -q` → **80 passed in 10.37s, 실패 0, 건너뜀 0**.

- 파일명/거부·키 파싱·설정 매핑/타입·환경변수 우선·원격 가드·재사용/중복/숫자·단위·순서·부분 실패.
- 실제 생성 DOCX/XLSX/PPTX를 docutranslate로 추출·되쓰기 후 다시 개방. 메모/시트명/수식/숫자 제외, 미디어 바이트 동일 확인.
- DOCX 각주·미주·텍스트 상자와 본문/표/머리글/바닥글. 굵게·기울임·색의 병합 한계 및 밑줄·형광펜·취소선·위첨자 경계 검증.
- XLSX 공유 문자열 중복 제거, 6종 머리글/바닥글과 제어 코드, 보완 시 다른 ZIP 파트 바이트 보존.
- 실제 Docxodus의 w:ins/w:del, daff 삽입 행/수식/시트 추가·삭제, PPTX 슬라이드·노트 위치 검증.
- rev001 두 언어 출력 → rev002 대기/승인 → 변경 원문만 전달. 반려·동일/상이 중복·낮은 rev·기준본 변경·실패 재시도.
- 두 번째 언어 실패 시 출력/메모리 미공개, 원문·키 없는 로그, Ctrl+C 복구, 차이 생성 중단과 뒤늦은 백그라운드 작업의 실패 전이.
- 실제 FastAPI TestClient로 목록·상세·문자 이스케이프·형식별 화면·승인/반려/재시도·URL 특수문자·정적 파일·경로/심볼릭 링크 탈출 차단.
- CLI process/watch/status/approve/reject/serve/check-translator 검증. check-translator 테스트와 별도 설치 CLI 실행도 fake 설정으로만 수행.

패키지 검증: 캐시된 setuptools를 사용해 네트워크·새 의존성 설치 없이 editable 설치 및 wheel 빌드 성공. 설치된 `.venv/bin/doc-translate`로 별도 임시 루트에서 process/status/check-translator를 실행해 두 언어 출력 확인. wheel 내부 Jinja2 템플릿과 CSS/JS 포함 확인.

웹 테스트 환경 제약: 샌드박스의 socketpair.send가 EPERM으로 거부되어 TestClient 이벤트 루프에 주기 타이머를 사용했습니다. 요청/라우팅/백그라운드 처리 코드는 대체하지 않았으며 실제 서버의 동작은 변경하지 않았습니다. 실제 포트로 브라우저에 접속하는 시험은 수행하지 않았습니다.

## 독립 검토와 수정

독립 읽기 전용 코드 검토에서 발견된 두 문제를 수정했습니다.

1. Ctrl+C가 `translating` 상태를 남김 → 부분 파일 정리·`failed` 저장 후 중단 전달. 회귀 테스트 실패 후 수정·통과 확인. 같은 위험이 있는 차이 생성 중단과 예약 작업이 최신 rev에 추월된 경우도 검사·수정.
2. upstream XLSX의 set 순서로 변경 건수 왜곡 → 추출 목록 안정 정렬. 단일 셀 추가 검증과 서로 다른 Python 해시 시드의 추출 결과 비교. 정렬 제거 시 실패하고 복구 시 통과함을 확인.

미처리 코드 검토 지적은 없습니다. 실제 API·키 파일·Office 화면·강제 종료 내구성은 독립 검토의 실행 범위에도 포함하지 않았으며 아래 한계로 남깁니다.

## 명세 보완과 결정

[design.md](../design.md)에 실제 반환형, 각주/미주 어댑터, XLSX 정렬, unresolved_errors 검사, 동일 문서 형식 고정, translating/failure_stage/notice, 통계 의미를 반영했습니다. 라이브러리 원본을 수정하거나 추출/되쓰기를 재구현하지 않았습니다. 기존 명세에 확정된 기술 선택을 따랐으므로 중복 ADR은 만들지 않았습니다.

기존 3.10/자체 XML 방식 계획은 최신 명세에 맞게 교체했습니다. 현재 상태와 한계는 [PROJECT_STATE.md](../../PROJECT_STATE.md), 구조는 [architecture.md](../../architecture.md), 실행법은 [README.md](../../../README.md)에 유지합니다.

## 남은 문제

- 실제 HiveAI 연결·번역 품질·Office 화면 배치는 사용자 실행/업무 문서 검증이 필요합니다. 실제 LLM/네트워크 호출과 저장소 밖 실제 키 파일 읽기는 하지 않았습니다.
- 문단 내부 일부 서식 손실은 upstream 한계로 유지합니다.
- SIGKILL·정전 후 여러 파일의 자동 복구는 제공하지 않습니다. 수동 복구 절차와 단일 작업 직렬화 제약은 PROJECT_STATE에 기록했습니다.
- 로그인·작업 큐·다중 작업자·번역문 수동 편집·메모 번역은 1차 범위 밖입니다.

기존 사용자 문서는 필요한 부분만 갱신했습니다. 작업 도중 별도로 나타난 `frontend/`, `docs/specs/frontend-react.md`, `docs/specs/deployment-intranet.md`는 이 구현에서 수정하거나 사용하지 않았습니다.
