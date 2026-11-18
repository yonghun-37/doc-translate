# doc-translate 구현 명세 (독립 작업 모델)

변경 위치·미리보기·진행 상황은 [layout-view.md](layout-view.md)가 우선합니다. 입력·저장·상태·매칭의 우선 명세는 [job-model.md](job-model.md)입니다. 기존 doc/rev 구조와 [web-upload.md](web-upload.md)는 대체되었습니다. 번역기 설정은 [translator-openai-compatible.md](translator-openai-compatible.md), 화면은 [frontend-react.md](frontend-react.md)를 따릅니다.

추출·되쓰기·LLM 호출은 **docutranslate**, DOCX 비교는 **python-redlines**, XLSX 비교는 **daff**를 재사용합니다. 라이브러리 소스를 복사하거나 수정하지 않습니다.

## 1. 결정 사항

| 항목 | 현재 규칙 |
| --- | --- |
| 처리 단위 | 한 번의 업로드 = 독립 job. 문서명·rev·이력·순서 제약 없음 |
| 입력 | 수정본(한국어) 필수, 원본(한국어)·기존 zh-CN·기존 zh-TW 선택. 모든 확장자가 동일 |
| 지원 형식 | docx·xlsx·pptx. 파일명 자유, 제목 기본값은 수정본 파일명 |
| 등록 | 번역 없이 검증·diff·기존본 매칭·번역 계획을 준비한 뒤 pending 공개 |
| 원본 없음 | 신규 문서 — 전체 번역. changes=[]; 형식별 diff 없음. 기존 중국어본이 있어도 재사용 불가 |
| 번역 | 언어별 기존본을 원본과 매칭해 완전 일치 원문을 재사용. 기존본 없는 언어는 전체 번역 |
| 실행 | 웹 [번역 실행] 확인 후 백그라운드 실행. 반려 사유 필수. failed 재시도 |
| 출력 | 수정본 구조를 유지한 `<수정본 stem>_zh-CN.ext`, `_zh-TW.ext`, 두 언어 모두 성공 후 공개 |
| 삭제 | translating 제외 모든 상태에서 확인 후 작업 전체 삭제 |
| 번역 요소 | 본문·표·텍스트 상자·머리글/바닥글·각주/미주·발표자 노트·슬라이드 마스터/레이아웃 |
| 제외 | 메모, 시트명, 수식, 숫자·단위만 있는 텍스트 |

## 2. 의존성 (버전 고정)

- Python 3.12 (`.venv/`는 이미 3.12로 만들어져 있고 아래가 설치돼 있음)
- `docutranslate==1.7.11` (MPL-2.0) — 추출·되쓰기·LLM 호출
- `python-redlines[docxodus]==2.0.0` (MIT) — docx 변경 추적 문서 생성
- `daff==1.4.2` (MIT) — 시트 표 비교·행 정렬
- `pypdfium2==5.15.2` (BSD-3-Clause·Apache-2.0 및 번들 고지) — PDF 페이지 PNG·텍스트. LibreOffice(MPL-2.0)는 서버에 별도 설치하는 외부 프로그램
- `python-multipart==0.0.34` — 이미 설치된 multipart 파서를 직접 의존성으로 명시
- `fastapi`, `uvicorn` — JSON API·정적 서빙; Vite·React·TypeScript는 frontend/package.json 고정 버전
- 개발: `pytest`, `httpx`, `openpyxl`, `python-docx`, `python-pptx`, `pillow`
- `pyproject.toml`에 위 버전을 그대로 고정합니다. 라이브러리 소스를 복사하거나 고치지 않습니다(MPL 파일 수정 금지). 동작을 바꿔야 하면 서브클래스·래퍼로 합니다.

## 3. 2026-11-17 사전 검증 결과 (구현 시 전제)

샘플 파일로 확인한 사실입니다. 테스트로 고정해 두세요.

- docutranslate의 `DocxTranslator`, `XlsxTranslator`, `PPTXTranslator`는 모두 `translate(document)` 안에서 `self.translate_agent.send_segments(texts, chunk_size)`를 **한 번** 호출하고 같은 길이의 리스트를 받아 되씁니다. `skip_translate=True`로 만든 뒤 `translator.translate_agent`에 우리 에이전트를 넣으면 LLM 없이 동작합니다.
- docx: 본문·표·머리글·바닥글이 세그먼트로 나오고 이미지 파트는 바이트 동일, 메모는 그대로 남음.
- xlsx: 문자열 셀만 나오고(공유 문자열은 중복 제거되어 1번), 수식·숫자·시트명·셀 메모·이미지는 그대로. **머리글·바닥글은 번역되지 않음** → 7.3절에서 보완.
- pptx: 제목·본문·발표자 노트와 함께 **슬라이드 마스터·레이아웃의 안내 문구**("Click to edit Master title style" 등)도 세그먼트로 나옴. 번역 대상에 두되 번역 재사용으로 비용은 기존 번역본이 없는 작업에서만 듭니다.
- docx 굵게·기울임·글자색은 "같은 서식"으로 보고 문장을 합쳐 번역하므로, 한 문단 안 일부 단어의 굵게 등은 사라지고 첫 run 서식을 따름(밑줄·형광펜·취소선·위첨자는 분리 보존). **라이브러리 설계이므로 그대로 두고** `docs/PROJECT_STATE.md`의 알려진 한계에 적습니다.
- python-redlines `DocxodusEngine().run_redline(author, old_bytes, new_bytes)` → 변경 추적(`w:ins`/`w:del`) docx 바이트. 1초 내외.
- daff로 시트 행 목록을 비교하면 끼워 넣은 행은 `+++`, 바뀐 셀은 `old->new`로 정확히 잡힘. 1차에는 `daff.DiffRender` HTML을 사용했으며, 2차 웹은 같은 hilite 결과를 JSON 행으로 전달합니다. 원문에 화살표가 있으면 daff의 가변 구분자를 유지합니다.

구현 중 확인한 보완 사항:

- `run_redline`의 실제 반환형은 `(docx_bytes, stdout, stderr)`이며 첫 항목을 산출물로 저장합니다.
- python-docx 1.2.0은 각주·미주를 일반 Part로 읽으므로, docutranslate 서브클래스에서 StoryPart로 연결한 뒤 upstream의 순회·되쓰기를 사용합니다. 라이브러리 파일은 수정하지 않습니다.
- xlsx 원문 추출은 집합 순서이므로 공통 세그먼트 비교 전에 정렬해 안정화합니다. 현재 변경 목록은 daff 행 정렬을 실제 셀 주소로 연결하며, 격자에서도 확인합니다.

## 4. 코드 구조

- `app/storage.py`: job ID/경로 검증, jobs·logs 생성, 원자적 JSON, 최신순 상태 목록.
- `app/inputs.py`: 표시용 파일명·Office ZIP 검증. rev 파일명 파싱 없음.
- `app/pipeline.py`: 입력 복사·검토 준비·작업 공개·번역 예약·반려·재시도·삭제, 파일 잠금.
- `app/alignment.py`: 위치 그룹/셀 주소 매칭, 최빈값 번역 기억, 미매칭 샘플과 번역 계획.
- `app/engine.py`, `app/locations.py`: 기존 docutranslate 래퍼·위치 표기.
- `app/reuse_agent.py`: 완전 일치 재사용, 누락 문장 중복 제거, 숫자 제외, 결과 검증.
- `app/xlsx_headers.py`: 동일 토큰화 경로로 머리글/바닥글 추출·번역. 해당 ZIP XML만 교체.
- `app/diff/`: 기존 공통 비교·DOCX redline·XLSX daff·PPTX 슬라이드 비교.
- `app/config.py`, `app/secure_agent.py`, `app/diagnostics.py`: 기존 LLM 설정/TLS/안전한 로그.
- `app/web/`: `/api/jobs` API, 4파일 스트리밍 수신, SPA 정적 서빙.
- `frontend/src/`: 기존 목록·업로드·상세 및 비교 컴포넌트, 번역 계획 표시.
- `app/cli.py`: serve·check-translator만 제공.

## 5. 기존 중국어본과 재사용

`engine.extract_with_locations`로 입력을 모두 검증·추출합니다. DOCX·PPTX는 연속된 같은 위치 키를 그룹화하고, SequenceMatcher(autojunk=False)로 위치 키 시퀀스를 정렬합니다. 일치한 그룹의 세그먼트 수가 같아야 순서대로 짝짓습니다. 수가 다르면 해당 그룹은 제외합니다.

XLSX는 openpyxl 읽기 전용으로 (시트, 셀 주소) 문자열을 연결합니다. 수식은 양쪽 모두 제외합니다. 동일 이름 시트를 우선 예약하고, 이름이 바뀐 시트는 같은 순서의 아직 대응하지 않은 시트와 연결합니다. 머리글/바닥글은 `xlsx_headers.extract`의 (시트, 종류)별 세그먼트 개수가 같을 때 순서대로 연결합니다. 출력은 openpyxl로 저장하지 않습니다.

빈 번역·원문과 같은 번역은 제외하고, 같은 원문의 후보 중 최빈값(동률은 먼저 나온 값)을 채택합니다. 언어별 memory에 원문이 존재하는 원본 추출 세그먼트를 matched로 셉니다. XLSX total은 셀 수가 아니라 upstream 추출 세그먼트 수입니다. 미매칭 최대 20개 위치·문장을 저장합니다. 기존본 없는 언어는 alignment 항목을 만들지 않으며, 원본 없이 기존본만 있으면 total=matched=0입니다.

`ReuseAgent`는 완전 일치 원문만 재사용하고 누락된 원문은 중복 제거하여 inner 에이전트로 보냅니다. 모든 입력은 불변이고 번역 기억은 작업별 `review/memory_<lang>.json`입니다. 다른 작업의 이력을 자동 선택하거나 메모리를 변경하지 않습니다.

언어별 계획·실행 통계의 `segments`는 추출 세그먼트 수, `reused`는 업로드에서 만든 기존 기억의 적중 횟수(숫자 제외), `translated`는 새로 보낸 고유 문장 수입니다. 같은 실행 안의 중복 캐시 적중은 reused에 포함하지 않습니다. 숫자·중복 때문에 세 수는 단순 합 관계가 아닙니다. 계획은 수정본 추출 결과와 기억으로 계산해 `review/plan.json`에 보관합니다.

위치 기반 매칭은 의미 검증을 하지 않습니다. 특히 사람이 DOCX 본문 중간에 문단을 삽입/삭제하여 뒤쪽 문단 번호가 바뀌면, 동일 위치 키·개수라도 잘못 대응할 수 있습니다. 위치 키가 유지되는 그룹 내 개수 변경은 그 그룹만 제외합니다. 매칭률은 번역 정확도 지표가 아니며, 복잡한 수동 편집본은 검토 후 사용해야 합니다.

## 6. LLM 연결 (docutranslate 설정으로)

`translator-openai-compatible.md`의 설정 표면(`base_url`, `model`, `api_key_env`, `api_key_file`, `allowed_hosts`, `ca_bundle`, `trust_env_proxy`, `temperature`, `max_tokens`, `timeout_sec`, `json_mode`, `extra_body`)은 유지하되, **HTTP 요청·묶음 내부 병렬화·재시도는 직접 만들지 않고** docutranslate `SegmentsTranslateAgentConfig`로 넘깁니다. 앱의 `progress_batch`(기본 40)는 진행 콜백을 위한 고유 새 문장 묶음 크기이며 ReuseAgent에 적용합니다.

- 매핑: `base_url→base_url`, `model→model_id`, 키→`api_key`, `temperature`, `timeout_sec→timeout`, `json_mode→force_json`, `extra_body`(여기에 `max_tokens` 병합), `retry`, `concurrent`(기본 4), `rpm`, `thinking="disable"`, `streaming`은 기본값.
- `to_lang`: zh-CN → `"简体中文"`, zh-TW → `"繁體中文（台灣）"`. 필요하면 `custom_prompt`에 "대만 표준 용어와 정자체" 같은 지시를 덧붙입니다.
- 용어집 `glossary/glossary.csv`(`source,zh-CN,zh-TW`)를 언어별 `glossary_dict`로 넘깁니다. `glossary_generate_enable`은 끕니다.
- 키 조회(환경변수 → 명시한 외부 키 파일의 이름표 제거), `allowed_hosts` 가드와 CA·프록시 설정, 로그에 원문·키 미기록은 `translator-openai-compatible.md` 2~3절대로 직접 구현합니다(작은 코드).
- 기본 예시는 `translator-openai-compatible.md` 2.0절의 사내 LLM 자리표시이며 `config.toml.example`에 둡니다. HiveAI는 `config.hiveai.toml.example`로 분리하고 `--config`로 선택합니다. 로컬 `config.toml`은 git 제외하며 자동 수정하지 않습니다. 이전 원격 허용 설정은 경고와 함께 해당 호스트만 허용 목록으로 옮겨 읽습니다. `json_mode=false`가 기본입니다(배열 응답과 json_object 충돌; 사용자 실측 12/12 성공).
- docutranslate가 부분 실패를 내면(예외, 결과 길이 불일치, `get_full_stats().unresolved_errors > 0`) 해당 작업은 `failed`, 출력 없음. 라이브러리의 원문 반환 fallback도 실패로 처리합니다.
- `doc-translate check-translator`: 설정 검증 후 한 문장을 zh-CN·zh-TW로 실제 번역해 출력.

## 7. 저장·처리 흐름

```text
jobs/<YYYYMMDD-HHMMSS-6자리hex>/
  status.json
  inputs/original.ext, revised.ext, base_zh-CN.ext, base_zh-TW.ext
  review/changes.json, redline.docx | sheets.json | slides.json
  review/alignment.json, memory_zh-CN.json, memory_zh-TW.json, plan.json
  output/<수정본 stem>_zh-CN.ext, <수정본 stem>_zh-TW.ext
logs/events.jsonl, library.log, .pipeline.lock, .uploads/, .docxodus/
```

job ID의 시각은 UTC입니다. 원본·기존본은 선택된 파일만 보관합니다. 파일명 메타데이터는 클라이언트 경로 성분을 제거합니다. 제목은 240자·이름은 200자 이내이며 빈 제목은 수정본 파일명, 빈 이름은 null입니다. 파일명은 제어 문자를 거부하며 출력 접미사와 파일시스템 제한을 고려해 UTF-8 240바이트 이내로 제한합니다.

### 등록

1. `logs/.uploads/`에서 multipart 스트리밍 수신. 파일별 50MB 기본값, 최대 4파일·2텍스트 필드(각 16KiB), 요청 전체 최대 `4 × 파일 한도 + 64KiB`. `serve --max-upload-mb`로 변경.
2. 확장자·ZIP CRC/필수 파트·내부 XML 문법·필드 검증. 모든 형식이 같아야 하며 원본과 수정본이 바이트 동일하면 400.
3. 파이프라인 잠금 안에서 고유 ID를 부여하고 요청 임시 공간의 job 폴더에 inputs를 복사. 이후 모든 입력을 추출해 손상을 검사.
4. 원본이 있으면 공통 변경 목록과 형식별 비교를 기존 도구로 생성. 매칭·기억·계획·status까지 준비.
5. job 폴더 전체를 `jobs/<id>`로 원자적 이동한 뒤 201. 실패·연결 중단 시 임시 파일 정리. 손상/준비 실패는 안전한 진단으로 400, 크기 초과는 413.

업로드·조회·서버 시작에는 번역 API 호출이 없습니다. 기존 데이터 이전·doc/rev 호환 API·CLI는 제공하지 않습니다. 임시 공간과 jobs는 같은 파일시스템이어야 원자적 이동이 가능합니다.

### 상태와 번역

`pending → translating → translated | failed`, `pending → rejected`, `failed → translating`입니다. approved·auto_approved 상태는 없습니다.

status에는 `id, title, ext, status, created_at, uploaded_by, decided_at, decided_by, reason, error, files, counts, alignment, stats, outputs`를 기록합니다. alignment는 언어별 total/matched 요약, stats는 언어별 통계, outputs는 job 기준 상대 경로입니다. 상세 API는 추가로 변경·매칭 샘플·계획·다운로드 URL을 제공합니다.

번역은 기존 ReuseAgent와 docutranslate를 조합합니다. XLSX headerFooter의 텍스트만 같은 에이전트로 처리하고 `&P`, `&N`, `&D`, 글꼴·크기 등 제어 코드를 유지합니다. 두 언어 파일을 job 안 임시 디렉토리에서 생성·검증한 뒤 output 디렉토리를 한 번에 이동하고 translated를 기록합니다. 일반 예외·Ctrl+C에는 부분 출력 제거 후 failed를 기록합니다. 재시도는 같은 입력·매칭 기억을 사용합니다.

`logs/.pipeline.lock`의 flock으로 변경·번역을 직렬화합니다. translating 삭제는 잠금 대기 전에도 검사해 409를 반환하고, 삭제 잠금 안에서 다시 확인합니다. 읽기는 원자적 상태 스냅샷을 사용합니다. 미리보기는 긴 파이프라인 잠금을 잡지 않고 별도 렌더 잠금을 사용합니다. 상태 필드 병합·미리보기 공개·삭제는 짧은 `.status.lock`으로 보호합니다. SIGKILL·정전 후 자동 복구/영속 큐는 제공하지 않습니다.

## 8. 웹·보안

[frontend-react.md](frontend-react.md)의 `/`, `/new`, `/jobs/:id`와 `/api/jobs`를 사용합니다. Host 허용 목록·동일 출처 검사·보안 헤더·스트리밍 제한을 유지합니다. DELETE도 동일 출처를 검사합니다. 다운로드는 해당 job의 redline.docx, ready 미리보기 PNG·overlays.json 또는 translated 상태에 공개한 출력만 허용하고 경로 탈출·심볼릭 링크를 차단합니다.

## 9. CLI

```bash
doc-translate serve --host 127.0.0.1 --port 8000 --max-upload-mb 50
# 인증 프록시가 전달하는 호스트를 허용하려면 --allowed-host HOST (반복 가능)
doc-translate --config /운영경로/config.toml check-translator
```

`--root` 또는 `DOC_TRANSLATE_ROOT`로 데이터 루트를 선택합니다. `--config` 기본값은 `<root>/config.toml`. process·approve·reject·retry·status·watch는 제공하지 않습니다.

## 10. 검증·범위

[작업 명세 6절](job-model.md#6-테스트)의 매칭·작업·업로드·화면 검증과 기존 엔진/서식/미디어·차이 도구·LLM 설정/TLS·안전한 진단 테스트를 실행합니다. 실제 API는 호출하지 않습니다.

```bash
.venv/bin/python -m pytest -q
cd frontend && npm test && npm run typecheck && npm run build
```

번역문 수동 편집, 로그인, 알림, 작업 큐·다중 작업자, 메모 번역, 문단 내부 부분 서식 개선은 범위 밖입니다.

## 11. 레이아웃과 진행 상태

`app/grid.py`는 읽기 전용 셀·스타일·병합·행/열 크기를 기존 daff 정렬과 연결합니다. `app/render.py`는 업로드 응답 뒤 LibreOffice → PDFium PNG와 Word 순차 페이지 매핑을 수행합니다. `app/slide_layout.py`는 기존 슬라이드 diff의 도형 좌표를 정규화하며 그룹은 바깥 그룹 경계를 사용합니다.

`[render] soffice="", timeout_sec=120, max_pages=300`을 지원합니다. 실행 파일은 환경변수 DOC_TRANSLATE_SOFFICE, 설정, PATH, /opt 순으로 탐색합니다. 호출별 프로필은 logs/.lo-profile/UUID, 임시 PDF/PNG는 logs/.render-*에서 준비하고 성공 후 review/preview에 공개합니다. Word PDF는 review/redline.pdf에 보관합니다. preview는 pending/ready/unavailable/failed이며 실패해도 작업 상태를 바꾸지 않습니다.

`app/progress.py`는 언어별 extract/reuse/llm/write/done·처리 개수·ETA·최근 50개 숫자 기록을 저장합니다. ReuseAgent의 progress_batch 기본값은 40입니다. 중간 저장은 초당 최대 1회, 최종 성공/실패는 즉시 저장하며 내용·키·응답은 기록하지 않습니다. 세부 계약과 제한은 layout-view.md 8절, 동시성 결정은 [ADR-004](../adr/ADR-004-layout-preview-and-progress.md)를 따릅니다.
