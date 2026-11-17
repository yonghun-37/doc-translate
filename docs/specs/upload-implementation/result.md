# 웹 업로드 구현 결과

## 완료한 기능

- [web-upload.md](../web-upload.md)의 웹 업로드·명시적 번역 실행 흐름을 구현했습니다. 신규 rev001도 `pending`, `base_rev=null`, 빈 변경 목록으로 등록하며 [번역 실행]을 확인해야 번역합니다. 기존 개정은 [승인 후 번역]을 사용합니다. 신규 반려에도 사유가 필요합니다.
- `GET /api/documents`는 최신/번역 완료/다음 rev와 차단 사유를 제공합니다. `POST /api/uploads`는 자유 파일명의 docx·xlsx·pptx를 받고 201 + ReviewDetail을 반환합니다. 올린 사람과 경로 성분을 제거한 원본 파일명을 저장·표시합니다.
- 웹의 중복 문서명·잘못된 이름·처리 중 판·기준본 없음·형식 불일치·동일 바이트·손상 파일을 거부합니다. 반려된 번호도 다음 rev 계산에 포함합니다. 등록 잠금 안에서 상태를 재검사하므로 동시 요청이 같은 번호를 덮어쓰지 않습니다.
- 설치된 Starlette/python-multipart 파서를 확장해 수신 파일을 `logs/.uploads/`에 쓰며 기본 50MB 한도를 수신 중 적용합니다. 초과하면 나머지 본문을 읽지 않고 413을 반환합니다. 검증·차이 생성 실패와 연결 중단은 임시 파일을 정리합니다.
- Pipeline 공통 등록 함수가 웹·process의 잠금·불변 원본·diff 준비/공개를 공유합니다. 업로드의 차이 생성이 실패하면 원본·검토 기록을 공개하지 않고 번호도 소비하지 않습니다.
- `/upload`의 신규 체크·문서명 자동 채움·기존 문서 선택 제한·rev 미리보기·전송 중 잠금·오류 배너·성공 후 상세 이동을 구현했습니다. 업로더와 승인자 이름은 같은 localStorage 값을 사용합니다.
- `watch` 명령, StableScanner, 감시 systemd 파일과 감시 테스트를 제거했습니다. `process`는 기존 파일명 기반 일괄 등록을 유지하고 rev001도 pending입니다. 등록할 때 번역기 검증·키 조회·LLM 호출을 하지 않습니다.

## 변경 파일

| 범위 | 파일과 역할 |
| --- | --- |
| 등록·CLI | `app/pipeline.py`, `app/cli.py`: 공통 등록·업로드 검사·대기 상태·크기 옵션. `app/watcher.py`를 제거하고 파일명/ZIP 검증만 `app/inputs.py`로 이동 |
| 웹 API | `app/web/__init__.py`, `app/web/models.py`, 신규 `app/web/uploads.py`: 문서 요약·업로드·메타데이터·스트리밍 파서 |
| 프론트 | `frontend/src/App.tsx`, `api.ts`, `pages/ReviewList.tsx`, `pages/ReviewDetail.tsx`, 신규 `pages/Upload.tsx`, `components/DecisionPanel.tsx`, 신규 `reviewer.ts`, `styles.css` |
| Python 테스트 | 신규 `tests/test_uploads.py`, `test_pipeline.py`, `test_web_cli.py`, `test_core.py`, `test_diagnostics_locations.py`: 업로드 계약·회귀·명시적 승인 전환 |
| 프론트 테스트 | 신규 `frontend/src/test/Upload.test.tsx`, `App.test.tsx`: 업로드·신규 실행 및 개정 버튼 문구 |
| 의존성·서비스 | `pyproject.toml`: 설치된 `python-multipart==0.0.34` 직접 선언. `deploy/doc-translate.service`: 크기 옵션 명시. `deploy/doc-translate-watch.service`: 삭제 |
| 현재 문서 | `README.md`, `docs/specs/design.md`, `frontend-react.md`, `deployment-intranet.md`, `docs/PROJECT_STATE.md`, `docs/architecture.md`: 입력·상태·운영 흐름과 잠금 파일의 실제 상태 반영 |
| 결정·개발 기록 | 신규 `docs/adr/ADR-002-web-upload-and-explicit-translation.md`, ADR-001에 후속 링크. 이 폴더의 plan/result. initial/second-implementation의 plan/result에는 과거 기록임을 알리는 안내만 추가하여 역사적 사실 보존 |

## 명세와의 차이 및 구체화

요청한 API·상태·화면 흐름의 미구현 항목은 없습니다. 명세에 세부 동작이 정해지지 않은 부분은 다음과 같이 구현하고 design.md·현재 상태에 기록했습니다.

- **관리자 process 호환:** 웹에 명시된 추가 거부 조건은 웹에 적용합니다. process의 여러 대기 판·기준본 없는 개정 일괄 등록은 유지하며, 기존 승인 시 기준본 재검사도 유지합니다. 자동 번역은 어느 등록 경로에서도 하지 않습니다.
- **차이 생성 실패:** 웹은 400 + 안전한 진단으로 거부하고 정리합니다. CLI는 기존처럼 원본·failed 상태를 남겨 retry할 수 있습니다. 웹의 실패 잔여 파일 금지와 CLI 복구 호환을 위한 구분입니다.
- **rev 상한:** 기존 Storage의 001~999 범위를 유지합니다. rev999의 next_rev는 1000으로 표시하되 blocked로 등록을 거부합니다.
- **multipart 부가 제한:** 파일의 정확한 바이트 한도 외에 요청 전체는 파일 한도 + 64KiB, 텍스트 필드는 각 16KiB·최대 3개, 파일은 1개로 제한합니다. 파일 외 데이터로 무제한 수신되지 않도록 한 구체화입니다. 업로더 이름은 기존 승인자 모델과 같은 최대 200자입니다.
- **의존성:** 새 패키지를 설치하거나 추가하지 않았습니다. 명세가 지정한 기존 python-multipart만 직접 의존성으로 선언했습니다. uv.lock은 사용자 요청대로 수정하지 않았습니다.

## 검증 결과

| 실행한 명령 | 결과 |
| --- | --- |
| `.venv/bin/python -m pytest -q` | **151 passed** |
| `cd frontend && npm test` | **24 passed**, 테스트 파일 3개 |
| `cd frontend && npm run typecheck` | 성공 |
| `cd frontend && npm run build` | 성공. 최종 CSS 정리 후 빌드도 재실행하여 성공 |

세 형식 신규 업로드→pending→승인→FakeAgent 번역, 개정 diff, 반려 번호 소비, 모든 거부 조건, 이름 경로 제거, 기존 원본 보존, 동시 신규/개정 등록, 크기 초과 조기 중단, 연결 중단, 잘린 multipart, 차이 생성 실패 시 정리를 검증했습니다. 기존 번역 재사용·두 언어 출력·실패 복구·API 회귀 테스트도 유지했습니다.

프론트는 신규/기존 폼·미리보기·선택 제한·성공 이동·전송 중 중복 제출 방지·오류 시 입력 유지·rev001 확인 후 실행을 검증했습니다. jsdom이 user-event의 파일 목록을 네이티브 required 검사에서 인식하지 못해 해당 테스트의 제출에서만 브라우저 기본 검증을 우회했습니다. 실제 버튼 클릭·앱 검사·서버 검증과 운영 폼의 required는 유지했습니다.

config.toml, uv.lock, frontend/package.json, frontend/package-lock.json은 작업 전후 SHA-256이 동일합니다. 실제 데이터 폴더의 원본은 수정하지 않았으며 테스트는 임시 디렉토리를 사용합니다. 패키지 설치·실제 LLM 호출·네트워크·Git 커밋·서비스 실행은 하지 않았습니다. 작업 시작 시 저장소 전체가 미추적 상태였으므로 변경 파일은 시작 시 파일별 해시와 비교했습니다.

## 남은 한계와 후속 작업

- uv.lock의 직접 의존성 반영은 사용자가 갱신·검토해야 합니다. 이전 감시 서비스가 운영 중이라면 관리자가 중지·비활성화·제거해야 합니다.
- 실제 브라우저 시각 확인, 사내 LLM·프록시·systemd·Office 화면 검증은 수행하지 않았습니다. 실제 LLM 연결은 사용자가 명시적으로 실행해야 합니다.
- 기존 단일 잠금 때문에 긴 번역 중 등록은 기다릴 수 있습니다. 업로드 크기는 압축 파일 기준이며 ZIP 해제 크기·문서 복잡도는 별도 제한하지 않습니다.
- 일반 실패·연결 중단은 정리하지만 SIGKILL·정전의 임시 파일 및 원본/상태 일괄 공개 복구는 자동화하지 않았습니다. 등록된 원본은 덮어쓰지 않습니다.
- multipart 서브클래스는 Starlette 내부 상태를 사용하므로 의존성 갱신 시 스트리밍·연결 중단·정리 테스트가 필요합니다. 나머지 문서 서식·번역 재사용·강제 종료 한계는 [현재 상태](../../PROJECT_STATE.md)를 따릅니다.
