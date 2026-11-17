# 1차 구현 계획

> 이전 구현의 기록입니다. 현재 입력은 [웹 업로드](../web-upload.md)로 전환했으며 감시·신규 자동 번역은 제거했습니다. 최신 상태는 [업로드 구현 결과](../upload-implementation/result.md)를 참고하세요.

기준: [구현 명세](../design.md). 현재 사용자 요청으로 명세와 실행 범위가 확정되어 있으므로 현재 디렉토리에서 직접 구현하며 커밋하지 않습니다. 구현 절차는 `executing-plans`, 동작 검증은 `test-driven-development`를 따릅니다.

## 목표와 구조

버전 등록 → 차이 검토 → 승인 → 간체·번체 출력 흐름을 구현합니다. `docutranslate==1.7.11`이 추출·되쓰기·HTTP·배치·재시도를 담당하고, 이 프로젝트는 에이전트 주입·재사용·파일 상태·검토 UI를 담당합니다. docx 비교는 `python-redlines[docxodus]==2.0.0`, xlsx 비교는 `daff==1.4.2`로 처리합니다.

제약: Python 3.12, 설치된 패키지만 사용, 한국어 문서/UI, 원본 불변, 개발·테스트 중 네트워크/실제 키 파일 접근 금지, 데이터 Git 제외. 커밋 없는 저장소의 사용자 제공 문서를 보존하며 기존 계획의 자체 XML 추출/Python 3.10 부분은 현재 명세로 대체합니다.

## 작업 및 인터페이스

- [x] 1. 기반: `config.py`, `storage.py`, `watcher.py`, `reuse_agent.py`, 패키지 설정. `parse_filename(name)`, `Config.load(root)`, `Storage(root)`, `ReuseAgent(memory, inner, recorder)`를 제공합니다. 파일명·키 파싱·원격 가드·중복 제거·숫자/단위 제외 테스트 실패 확인 후 구현합니다.
- [x] 2. 문서 엔진: `engine.extract(path) -> list[str]`, `engine.translate(path, agent) -> bytes`, `xlsx_headers.transform(content, agent) -> bytes`. 라이브러리를 기록용 에이전트로 실행해 추출하며, 보완은 sheet XML의 headerFooter에만 적용합니다. 세 형식의 실제 생성 fixture로 텍스트·메모·수식·이미지·부분 서식·머리글 제어 코드 보존을 검증합니다.
- [x] 3. 비교: `diff.segments.compare(old, new)`, 형식별 `build(old_path | None, new_path, destination)`. 세그먼트 JSON, Docxodus 변경 추적, daff HTML, python-pptx 위치별 변경을 검증합니다.
- [x] 4. 파이프라인: `Pipeline.process()`, `approve(doc, rev, by, background=False)`, `reject(doc, rev, reason, by)`, `retry(doc, rev, background=False)`, `translate(doc, rev)`. 기준본은 번역 완료 rev만 사용합니다. 두 언어의 결과와 메모리는 모두 성공한 뒤 공개하며 실패 시 부분 출력은 삭제합니다. 승인 경합·기준본 변경·반려·실패 복구를 검증합니다.
- [x] 5. 웹/CLI: `create_app(root, pipeline=None)`, `cli.main(argv=None)`. 한국어 목록·상세·문자 강조·승인/반려/재시도·안전한 다운로드와 모든 CLI 명령을 연결하고 TestClient로 검증합니다. 웹은 시스템 글꼴·로컬 CSS/JS·키보드 포커스·명시적인 폼 레이블을 사용합니다.
- [x] 6. 전체 검증, 독립 코드 검토, README·PROJECT_STATE·결과 문서 갱신. `.venv/bin/python -m pytest -q`의 실제 결과를 기록합니다.

## 검토 초점

- 같은 문서/rev의 형식 변경·상이한 내용·낮은 rev는 거부하고 동일 파일만 멱등 처리.
- 앞부분 삽입에도 원문 문자열 완전 일치로 재사용하며 새 세그먼트 중복은 한 번만 전송.
- 두 번째 언어 실패 및 라이브러리의 원문 반환 fallback을 실패로 인식해 부분 출력 금지.
- 대기 중 기준본이 바뀌면 재검토를 요구하고 실패 재시도가 승인 절차를 건너뛰지 않음.
- 파일명·본문의 HTML 특수문자와 다운로드 경로/심볼릭 링크 탈출을 차단.

## 구현 판단 및 진행 근거

- 초기 확인: 코드와 테스트는 없고 문서만 미추적 상태입니다. Python 3.12.13 및 지정 라이브러리 버전을 확인했습니다.
- `DocxodusEngine.run_redline`의 실제 반환값은 `(bytes, stdout, stderr)`이므로 첫 항목만 저장합니다.
- docutranslate는 일부 실패에 원문을 반환할 수 있어 `get_full_stats().unresolved_errors`도 검사합니다. 라이브러리 로그는 전용 무출력 logger로 차단하고 앱에는 상태와 수치만 기록합니다.
- `extra_body`는 docutranslate 설정에서 JSON 문자열이므로 직렬화하여 전달합니다. 독자적인 HTTP·배치·재시도 코드는 작성하지 않습니다.

## 완료 근거

- 기반 테스트 36개, 엔진 8개, 비교 4개, 파이프라인 17개, 웹/CLI 15개: 전체 80개 통과.
- 독립 검토의 XLSX 순서 불안정과 Ctrl+C 상태 잔류를 회귀 테스트로 수정했습니다.
- 키의 `=` 보존·설정 타입 검사·단위/지수 숫자 제외, 뒤늦은 작업 및 diff 중단 처리도 검증했습니다.
- 오프라인 editable 설치·wheel 빌드·설치 CLI 실행·정적 파일 포함을 확인했습니다.
- 선택한 방식과 비용: 각주 어댑터와 부분 실패 통계는 고정된 라이브러리 계약에 의존하므로 업그레이드 시 엔진 회귀 테스트가 필요합니다. XLSX 정렬로 세그먼트 순서는 셀 위치를 뜻하지 않으며 위치는 daff로 제공합니다.
- 강제 종료/정전 자동 복구는 1차에 추가하지 않았으며 수동 복구 비용을 PROJECT_STATE에 명시했습니다.
- 상세 결과와 남은 검증은 [result.md](result.md)에 기록했습니다.
