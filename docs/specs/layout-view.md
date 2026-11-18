# 변경 위치 표기 · 원래 모양 미리보기 · 번역 진행 상황

2026-11-18 사용자 결정. `job-model.md` 위에 얹는 기능이며 충돌 시 이 문서가 우선합니다.

## 1. 결정

| 항목 | 결정 |
| --- | --- |
| 변경 위치 | 엑셀 = 시트·셀 주소, 워드 = 페이지(+ 그 페이지의 몇 번째 문단), PPT = 슬라이드 번호·도형 종류 |
| 원래 모양 보기 | 엑셀 = 웹에서 엑셀 같은 격자(열 문자·행 번호·시트 탭)에 바뀐 셀 강조. 워드 = 변경 추적 문서(redline.docx)를 페이지 이미지로. PPT = 원본·수정본 슬라이드 이미지를 나란히, 바뀐 도형에 테두리 |
| 렌더링 | LibreOffice(서버에 설치, 외부 프로그램 호출) → PDF → pypdfium2(5.15.2, BSD-3/Apache-2.0, 설치·잠금 완료)로 PNG |
| 진행 상황 | 번역 중 단계·언어별 진행 막대·경과/예상 시간·최근 기록(숫자만) |

2026-11-18 실측: LibreOffice 26.2.7로 redline.docx → PDF 2.8초. 삽입은 색 밑줄, 변경 줄 왼쪽에 변경 막대가 Word 변경 추적과 비슷하게 보임. pypdfium2로 PNG 렌더링·페이지 텍스트 추출 정상.

## 2. LibreOffice 호출 (`app/render.py`)

- 실행 파일: 환경변수 `DOC_TRANSLATE_SOFFICE` → 설정 `[render] soffice` → PATH의 `soffice`/`libreoffice` → `/opt/libreoffice*/program/soffice` 순. 없으면 미리보기 `unavailable`(오류 아님), 위치는 3절의 대체 표기.
- 호출: `soffice --headless --norestore --nolockcheck -env:UserInstallation=file://<logs/.lo-profile/<uuid>> --convert-to pdf --outdir <임시> <파일>`. 호출마다 별도 프로필(동시 실행 충돌 방지), 끝나면 삭제. 제한 시간 120초(`[render] timeout_sec`), 초과 시 프로세스 그룹 종료. 동시에 하나만 실행(잠금). 셸을 쓰지 않고 인자 목록으로 실행.
- PNG: 긴 변 1600px 기준 배율, 문서당 최대 300페이지(`[render] max_pages`). 초과분은 렌더링하지 않고 안내.
- 업로드 응답을 늦추지 않도록 diff 생성 후 **백그라운드**로 미리보기를 만든다. status.json `preview: {status: pending|ready|unavailable|failed, message, pages}`. 실패해도 작업 자체는 `pending` 그대로(번역 가능).
- 작업 폴더: `review/preview/redline-001.png …`(docx), `review/preview/original-001.png`, `revised-001.png`, `review/preview/overlays.json`(pptx), `review/redline.pdf`.

## 3. 변경 위치 표기 (`changes.json`의 `where`)

- **엑셀:** `'단가' 시트 · B3`. 머리글·바닥글은 `'단가' 시트 · 머리글(가운데)`. 시트 추가·삭제는 `'단가' 시트 전체`. openpyxl 읽기 전용으로 셀 주소를 얻는다(출력 파일 저장 금지 규칙 유지). 추가 행은 수정본 주소, 삭제 행은 원본 주소 + "(원본)".
- **워드:** redline.pdf에서 페이지를 찾는다. 변경 목록 순서대로 각 문단 텍스트(공백 정규화)를 PDF 페이지 텍스트에서 **앞에서부터 순차 탐색**해 같은 문구가 여러 번 나와도 올바른 페이지에 대응. 표기 `3페이지 · 2번째 문단`, 표는 `3페이지 · 표 1 · 2행 2열`, 머리글·바닥글·각주는 `머리글`, `각주 2`처럼 페이지 없이. 페이지를 못 찾거나 LibreOffice가 없으면 지금의 `본문 문단 N`. 페이지는 미리보기 완료 후 채워지므로 `changes.json`을 그때 갱신한다(`page` 필드 추가).
- **PPT:** `슬라이드 3 · 제목`, `슬라이드 3 · 본문`, `슬라이드 3 · 표 2행 1열`, `슬라이드 3 · 발표자 노트`, 그 외는 `슬라이드 3 · 도형 "이름"`. 마스터·레이아웃은 `마스터 1 · 제목` 형식 유지.
- `Change`에 선택 필드 추가: `page?: number`(docx), `slide?: number`(pptx), `sheet?: string, cell?: string`(xlsx). 화면에서 해당 위치로 이동하는 데 쓴다.

## 4. 원래 모양 보기 (화면)

상세 화면의 변경 영역에 탭 두 개: **[원래 모양]**(기본) · **[변경 목록]**(기존 표). 변경 목록 행을 누르면 원래 모양 탭의 해당 위치로 이동.

- **엑셀 `SheetView`** (새 의존성 없이 직접 구현): API `GET /api/jobs/{id}/grid` → 시트별 `{name, status, cols:[{letter,width}], rows:[{index,height,cells:[{addr,value,bold?,italic?,fill?,color?,align?,span?}] }], merges, changes:{addr:{op,old,new}}, removed_rows:[{after,cells}]}`. 수정본 기준, 값은 표시 값(가능하면 캐시된 계산 결과, 없으면 수식 문자열). 바뀐 셀 노랑, 추가 행 초록, 삭제된 행은 해당 위치에 빨간 얇은 줄 + 펼치면 원본 행. 셀에 마우스를 올리면 `이전 → 새 값`. 열 문자·행 번호 고정 머리, 아래 시트 탭(바뀐 시트에 점 표시), [이전 변경]·[다음 변경] 버튼. 시트당 최대 2,000행 × 100열 표시, 초과 시 안내(변경 셀 주변은 항상 포함).
- **워드 `PageView`:** redline 페이지 이미지를 세로로, 왼쪽에 페이지 썸네일(변경 있는 페이지 표시). 페이지 머리에 "3페이지 — 변경 2건". 이미지 지연 로딩. 범례: 색 밑줄 = 추가, 취소선 = 삭제.
- **PPT `SlideCompare`:** 슬라이드별로 원본 | 수정본 이미지를 나란히, `overlays.json`의 바뀐 도형 위치에 테두리(추가 초록, 수정 주황, 삭제 빨강; 삭제는 원본 쪽에). 위치는 python-pptx 도형 좌표(EMU)를 슬라이드 크기 비율로. 그룹 도형은 그룹 경계. 발표자 노트 변경은 이미지 아래 텍스트로. 바뀐 슬라이드만 보기 토글.
- 미리보기 `pending`이면 "미리보기 만드는 중" + 3초 폴링, `unavailable`이면 "서버에 LibreOffice가 없어 원래 모양 보기를 할 수 없습니다" 안내 후 변경 목록 탭.
- 이미지 파일은 `GET /api/jobs/{id}/files/preview/<name>`(작업 폴더 밖 차단 규칙 유지).

## 5. 번역 진행 상황

- `ReuseAgent`가 LLM에 보낼 문장을 **묶음 단위**(`[translator.openai_compatible] progress_batch`, 기본 40)로 나눠 내부 에이전트 `send_segments`를 묶음마다 호출하고, 콜백으로 진행을 알린다(묶음 안의 병렬 처리는 docutranslate 그대로).
- status.json `progress`: `{phase: "extract"|"reuse"|"llm"|"write"|"done", langs: {lang: {phase, total, reused, translated, done}}, started_at, updated_at, eta_sec, log: [{at, message}]}`. 로그는 최근 50개, **문서 내용 없이 숫자·단계만**(예: "간체 LLM 묶음 3/5 완료 (40문장, 6.2초)", "번체 기존 번역 재사용 9문장"). 저장은 최대 초당 1회, 원자적 쓰기.
- 예상 시간: 완료된 묶음 평균 속도 × 남은 문장 수. 첫 묶음 전에는 "계산 중".
- 화면 `TranslationProgress`: 단계 표시(문서 읽기 → 기존 번역 재사용 → LLM 번역 → 파일 만들기), 언어별 막대(`재사용 9 + 번역 40/120`), 경과·남은 예상 시간, 최근 기록 목록. 2초 폴링(기존). 실패 시 마지막 기록과 오류 표시.

## 6. 배포·라이선스

- 운영 서버: `libreoffice-writer-nogui libreoffice-impress-nogui fonts-noto-cjk`(Debian/Ubuntu) 또는 공식 tarball 설치. 한글·중국어 글꼴이 없으면 모양이 크게 달라진다. 문서에 쓰인 회사 글꼴(맑은 고딕 등)은 라이선스가 허락하면 서버에 설치 권장. LibreOffice는 MPL-2.0이며 외부 프로그램으로 호출만 하고 저장소에 포함하지 않는다.
- 개발 PC(이 저장소의 WSL): 공식 LibreOffice 26.2.7을 `~/.local/opt/lo/opt/libreoffice26.2/program/soffice`에 사용자 설치, `DOC_TRANSLATE_SOFFICE`로 지정.
- THIRD_PARTY_LICENSES.md에 pypdfium2 추가, LibreOffice는 외부 실행 프로그램으로 명시. deployment-intranet.md·README 갱신.

## 7. 테스트

- 오프라인·LibreOffice 없이 도는 단위 테스트가 기본: 렌더러는 가짜 PDF 생성기로 대체(pypdfium2로 만든 PDF 또는 미리 만든 작은 PDF 픽스처).
- `DOC_TRANSLATE_SOFFICE`가 있으면 실행되는 통합 테스트(없으면 skip): docx redline 페이지 이미지·페이지 번호, pptx 슬라이드 이미지·overlay.
- 위치 표기: xlsx 셀 주소(행 삽입 후에도 수정본 주소), docx 순차 페이지 탐색(같은 문구 2회), pptx 도형 종류.
- grid API: 값·병합·열 너비·변경 셀·삭제 행·크기 제한.
- 진행 상황: 묶음 분할·콜백·ETA·로그에 원문 없음·초당 1회 저장.
- 프론트: SheetView 강조·툴팁·시트 탭·이전/다음, PageView, SlideCompare overlay, 변경 목록 → 위치 이동, 미리보기 pending/unavailable, TranslationProgress.

## 8. 구현 시 구체화

- `preview.pages`는 `{page, name, width, height, side}` 배열입니다. `side`는 redline/original/revised이며 이미지 URL은 기존 작업 파일 API에서 만듭니다. 원본 없는 신규 문서는 기존 작업 모델대로 비교를 만들지 않습니다. 이 기능 도입 전 preview 필드가 없는 작업은 기존 변경 목록을 유지합니다.
- XLSX `source: original|revised`를 변경에 추가해 삭제 행의 원본 셀과 수정본의 같은 주소를 구분합니다. daff의 정렬 대응은 sheets.json의 `row_pairs`에 함께 보관합니다. 격자에는 행 추가 여부·삭제 원본 행 번호·제한 안내를 추가합니다.
- 2,000행/100열을 넘는 **서로 다른 변경 위치 전부**를 동시에 표시하는 것은 한도와 충돌하므로 변경 위치·이웃·처음 부분 순서로 선택합니다. `/grid?sheet=...&row=...&col=...`은 요청 위치를 가장 먼저 포함하며 변경 목록에서 이동할 때 사용합니다. 기본 범위에서 생략된 위치도 목록에서 선택할 수 있습니다. 셀은 캐시된 수식 결과를 우선하고 없으면 수식 문자열을 표시하며, Excel의 모든 사용자 지정 숫자 서식·조건부 서식은 재현하지 않습니다.
- Word는 변경 없는 문단도 포함한 redline 순서로 탐색하여 반복 문구의 페이지를 구분합니다. 변경 추적에서 보이는 전체 텍스트와 원본/수정본 텍스트를 순서대로 후보로 사용합니다. 매칭할 수 없는 문단은 명세의 기존 위치로 남깁니다.
- 진행 `total`은 재사용 예정 발생 횟수 + 새 번역 고유 문장 수, `done`은 재사용 완료 + 새 번역 완료입니다. 숫자·중복 때문에 전체 추출 세그먼트 수와 다를 수 있습니다. ETA는 두 언어의 남은 새 번역 문장에 완료 묶음의 문장당 평균 시간을 곱하며 추출·파일 생성 시간은 포함하지 않습니다.
- **중간 진행 저장**은 최대 초당 1회입니다. 완료/실패 전환에는 마지막 기록 유실을 막고 실제 상태를 즉시 공개하기 위해 제한과 별개로 최종 스냅샷을 저장합니다. 별도 진행 타이머·영속 큐는 도입하지 않습니다.
