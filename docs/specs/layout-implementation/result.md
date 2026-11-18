# 레이아웃 보기·변경 위치·번역 진행 구현 결과

기준: [layout-view.md](../layout-view.md). 구현 날짜: 2026-11-18. **코드·오프라인 검증은 구현했으나 실제 LibreOffice 통합 성공과 수동 화면 확인이 남아 있어 전체 완료 조건은 아직 충족하지 못했습니다.**

## 구현한 기능과 주요 파일

| 영역 | 변경 파일과 내용 |
| --- | --- |
| 렌더링 | `app/render.py`: 실행 파일 탐색, 독립 프로필, 셸 없는 실행, 시간 제한·프로세스 그룹 종료, 직렬 실행, PDFium PNG·텍스트, Word 순차 페이지 매핑, 준비 후 공개 |
| 위치·격자 | `app/grid.py`, `app/diff/xlsx.py`, `app/locations.py`, `app/xlsx_headers.py`, `app/slide_layout.py`: daff 행 대응과 실제 셀 주소, 읽기 전용 스타일·병합·수식 캐시·삭제 행·표시 제한, 머리글/바닥글 위치, PPT 도형 종류·좌표·그룹 경계 |
| 상태·설정 | `app/pipeline.py`, `app/storage.py`, `app/config.py`: 업로드 후 미리보기, 독립 preview 상태, 짧은 상태 잠금으로 삭제/번역 경합 보호, `[render]`와 progress_batch |
| 번역 진행 | `app/reuse_agent.py`, `app/progress.py`: 기본 40개 고유 새 문장 묶음, 숫자 콜백, 언어별 단계·완료 수·ETA, 최근 50개 기록, 중간 저장 제한 |
| API | `app/web/__init__.py`, `app/web/models.py`: grid API와 위치 query, preview PNG/overlays.json 제공, Change 위치 선택 필드, preview/progress 상세 응답, 이미지 self CSP |
| 화면 | `frontend/src/api.ts`, `pages/ReviewDetail.tsx`, `components/ChangeTable.tsx`, `styles.css`; 새 `LayoutView`, `SheetView`, `PageView`, `SlideCompare`, `TranslationProgress`: 원래 모양 기본 탭, 변경 목록에서 이동, 형식별 보기, 미리보기 3초/번역 2초 폴링, 키보드 조작·지연 로딩·숫자 진행 표시 |
| 테스트 | `tests/test_layout.py`, `frontend/src/test/Layout.test.tsx`: 새 동작·경계·경합·UI 이동과 실제 LibreOffice 조건부 통합 |
| 문서 | README, design, frontend-react, deployment-intranet, PROJECT_STATE, architecture, layout-view 8절, 두 config 예시, THIRD_PARTY_LICENSES 및 생성 스크립트, [ADR-004](../../adr/ADR-004-layout-preview-and-progress.md), 이 폴더의 계획·결과 |

추출·되쓰기·번역 출력 생성은 기존 docutranslate 경로를 유지했습니다. XLSX 출력 보완은 기존 ZIP XML 교체 그대로이며 openpyxl로 출력/입력을 저장하지 않습니다. 기존 입력·기억은 불변입니다. 라이브러리 소스는 복사·수정하지 않았습니다.

## 명세에서 구체화하거나 조정한 점

- 격자 한도보다 서로 다른 변경 행/열이 많으면 모든 변경을 동시에 포함할 수 없습니다. 기본 응답은 변경 위치·이웃·처음 부분 순서로 최대 2,000행 × 100열을 선택하고, 변경 목록의 위치 이동은 `/grid?sheet=...&row=...&col=...`로 해당 위치를 우선 포함합니다. 병합에 가려진 변경 주소는 병합 시작 셀에 표시·포커스합니다.
- `row_pairs`를 sheets.json에 저장해 daff 정렬을 재사용합니다. 삭제 셀의 source, 행 추가 여부, 삭제 원본 행 번호, 병합 안의 변경 주소를 부가 필드로 제공합니다. 원본 없는 신규 작업은 기존 명세대로 비교/미리보기를 생략하고, 이전 preview 없는 작업은 기존 목록을 유지합니다.
- Word는 반복 문구를 구분하기 위해 변경 없는 문단도 포함한 redline 문단 순서로 PDF를 검색합니다. 전체 변경 추적 텍스트와 원본/수정본을 후보로 쓰며 찾지 못하면 기존 위치를 유지합니다. 표/텍스트 상자 등 복잡한 배치의 정확한 조판 좌표 매핑을 새로 구현하지 않았습니다.
- 진행 total은 재사용 예정 발생 횟수 + 새 번역 고유 문장 수입니다. ETA는 두 언어의 남은 새 문장 수와 완료 묶음의 문장당 평균 시간 기준이며 추출/파일 생성 시간은 제외합니다.
- 중간 진행 저장은 최대 초당 1회입니다. **최종 완료/실패 전환은 마지막 기록을 잃지 않고 실제 상태를 공개하기 위해 즉시 저장**합니다. 이 예외와 위 필드는 layout-view.md 8절과 PROJECT_STATE에 기록했습니다.
- 사용자 설치 LibreOffice의 실행 실패를 이유로 통합 테스트를 추가 skip하거나 성공으로 처리하지 않았습니다. 이는 명세 변경이 아니라 미해결 검증 항목입니다.

## 검증 결과

| 실행 | 결과 |
| --- | --- |
| `.venv/bin/python -m pytest -q` (DOC_TRANSLATE_SOFFICE 미지정) | **179 passed, 2 skipped** — 통합 2건만 조건부 skip |
| `DOC_TRANSLATE_SOFFICE="$HOME/.local/opt/lo/opt/libreoffice26.2/program/soffice" .venv/bin/python -m pytest -q` | **179 passed, 2 failed** — DOCX/PPTX 실제 변환 통합 실패 (종료 코드 1) |
| `cd frontend && npm test && npm run typecheck && npm run build` | **34개 테스트·타입 검사·운영 빌드 성공** |
| `git diff --check` | 통과 |
| 시작 시 SHA-256과 비교 | config.toml, uv.lock, pyproject.toml, frontend/package.json, frontend/package-lock.json 동일 |

오프라인 검증 범위:

- 셀 주소와 행 삽입/삭제, 수식 캐시/수식 문자열, 병합·굵기·색·너비·높이, 크기 제한 밖 변경, grid API·입력 불변.
- PDFium 실제 PNG 생성과 1600px/페이지 제한, 반복 문구 순차 탐색, Word 변경 목록 페이지 보완.
- PPT 제목/표/노트 위치·그룹 경계, 미리보기 공개·PNG MIME·CSP·경로/심볼릭 링크 차단.
- 별도 프로필·셸 없는 인자·시간 초과 그룹 종료, 직렬 렌더 잠금, 미설치/실패 처리, 삭제 중 작업 재생성 방지, 미리보기와 번역 동시 완료 시 상태 보존.
- 묶음 분할/중복 캐시/결과 검증, 숫자 콜백·ETA·50개 기록·중간 저장 빈도. 기존 네트워크 차단 fixture와 FakeAgent 유지.
- 프론트 강조·툴팁·HTML 이스케이프·시트 전환·이전/다음·삭제 펼치기·병합/삭제 위치 포커스, 페이지/썸네일·슬라이드 overlay/노트/필터, 목록→페이지 이동, pending 폴링/중지·unavailable/failed 대체·진행 막대/ETA/마지막 기록.

## 실제 실행 확인과 남은 한계

- 지정한 soffice의 `--version`은 **LibreOffice 26.2.7.3**으로 정상 출력됩니다. 그러나 임시 DOCX/PPTX 작업과 직접 실행한 headless PDF 변환은 **출력 없이 종료 코드 1**, PDF 미생성으로 실패했습니다. 이 샌드박스의 AF_UNIX/AF_INET 소켓 작업은 `PermissionError: EPERM`이며 strace도 ptrace 제한으로 실행되지 않았습니다. LibreOffice 내부 실패 원인은 직접 확정하지 못했습니다. 제한이 없는 로컬 셸에서 같은 통합 명령을 재실행해야 합니다.
- 설치된 Chromium으로 수동 화면 확인을 시도했으나 시작 시 `sandbox_host_linux.cc: shutdown: Operation not permitted`로 종료했습니다. 실제 Word/PPT 페이지의 모양과 브라우저 시각·반응형 검토는 확인하지 못했습니다. 테스트에서 생성한 가짜 PDF는 렌더러/API 검증용이며 실제 LibreOffice 검증을 대신하지 않습니다.
- 서버 글꼴·LibreOffice 조판에 따라 Office와 배치가 다릅니다. 페이지에 걸친 문단·복잡한 추적 변경·추출 불일치 시 Word 페이지 표기가 남지 않을 수 있습니다. 서버에 Noto CJK와 허용된 회사 글꼴을 설치해야 합니다.
- XLSX는 Excel의 모든 숫자 서식·테마 색·조건부 서식·차트/그림을 재현하지 않습니다. 행/열 크기는 웹 표시 단위로 변환합니다. PPT의 순수 도형 이동·서식/이미지 변경은 기존 텍스트 diff 범위 밖입니다.
- 최대 표시 페이지 밖의 위치, PPT 마스터/레이아웃 변경은 목록에서 확인합니다. 렌더링 중 강제 종료 시 pending 자동 재개는 제공하지 않으며 임시 공간 정리 후 새 작업 등록이 필요합니다.

네트워크·실제 LLM 호출·패키지 설치·Git 커밋은 하지 않았습니다. 사용자가 미리 변경한 pyproject.toml·uv.lock과 로컬 config.toml을 그대로 보존했습니다.
