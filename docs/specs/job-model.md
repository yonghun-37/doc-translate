# 작업 단위 모델: 원본·수정본·기존 중국어본을 한 화면에서 올리기

2026-11-17 사용자 결정. `web-upload.md`(문서명·rev 이력 + 한 파일 업로드)를 **대체**합니다. `design.md`·`frontend-react.md`의 doc/rev 관련 규칙도 이 문서가 우선합니다.

## 1. 결정

| 항목 | 결정 |
| --- | --- |
| 단위 | **작업(job) 1건 = 한 번의 업로드.** 문서명·rev 번호·문서별 이력·순서 제약 없음 |
| 업로드 | 한 화면에서 **원본(한국어)**, **수정본(한국어, 필수)**, **기존 중국어본 zh-CN·zh-TW(각각 선택)** 을 함께 올림. 원본을 비우면 신규 문서(전체 번역, 차이 없음) |
| 흐름 | 업로드 → 원본↔수정본 diff와 기존 중국어본 매칭 결과를 화면에서 확인 → [번역 실행] 또는 [반려] → 번역 → 내려받기 |
| 번역 범위 | 언어별로: 기존 중국어본이 있으면 원본 문장↔중국어 문장을 매칭해 **안 바뀐 문장은 기존 번역 그대로**, 바뀌었거나 매칭 안 된 문장만 LLM 번역. 기존본이 없는 언어는 수정본 전체 번역 |
| 결과 | 수정본 구조 그대로의 중국어 파일(`<수정본 파일명>_zh-CN.ext`, `_zh-TW.ext`). 출력 파일은 지금처럼 docutranslate가 생성 |
| 제거 | doc/rev 개념, `versions/`·`review/`·`output/`·`inbox/` 폴더, `process`·`approve`·`reject`·`retry` CLI, `/api/documents`, 파일명 규칙(`_revNNN`). `serve`·`check-translator`는 유지 |

## 2. 기존 중국어본 매칭 (번역 기억 만들기)

목표: 원본 한국어 세그먼트 텍스트 → 기존 중국어 텍스트의 사전(`ReuseAgent` memory와 같은 형식)을 언어별로 만든다. docutranslate 추출(`engine.extract_with_locations`)을 그대로 사용하고 라이브러리를 수정하지 않는다.

- **docx·pptx:** 원본과 중국어본을 각각 추출해 위치 키(`본문 문단 3`, `슬라이드 1 · Title 1` 등) 순서로 비교. `difflib.SequenceMatcher`로 위치 키 시퀀스를 정렬하고, 같은 위치 키 그룹 안에서 세그먼트 수가 같으면 순서대로 짝짓는다. 수가 다르면 그 그룹은 매칭하지 않는다(→ 새 번역). 2026-11-17 실측: 우리 시스템이 만든 번역본은 docx 11/11, pptx 65/65가 위치 키·개수 모두 일치.
- **xlsx:** 추출 순서가 원본과 번역본에서 다르므로 위치 순서를 쓰지 않는다. openpyxl로 두 파일을 **읽기 전용**으로 열어 (시트 이름, 셀 주소)가 같은 문자열 셀끼리 짝짓는다(수식 `=`로 시작하는 값 제외). 머리글·바닥글은 `app/xlsx_headers.py`의 추출 경로로 (시트, 종류) 단위로 짝짓는다. 시트 이름이 번역되어 다르면 시트 순서로 대응.
- 한 원문이 여러 번역과 짝지어지면 가장 많이 나온 번역(동률이면 첫 번째)을 쓴다. 원문과 번역이 같거나 번역이 비어 있으면 사전에 넣지 않는다(→ 새 번역).
- 결과 통계를 언어별로 저장·표시: `{lang, total: 원본 세그먼트 수, matched, unmatched_samples: 최대 20개 [{where, text}]}`. 매칭률이 낮으면(예: 50% 미만) 화면에 경고 배너.
- 기존 중국어본의 형식(확장자)이 수정본과 다르면 업로드 거부(400).

## 3. 상태·저장

```
jobs/<job_id>/            # job_id = YYYYMMDD-HHMMSS-<6자리 무작위>, 경로 성분 검증
  status.json
  inputs/original.<ext>, revised.<ext>, base_zh-CN.<ext>, base_zh-TW.<ext>   # 쓰기 후 불변
  review/changes.json, redline.docx | sheets.json | slides.json, alignment.json, memory_zh-CN.json, memory_zh-TW.json
  output/<수정본 stem>_zh-CN.<ext>, ..._zh-TW.<ext>
logs/                      # 기존 그대로 (events.jsonl, 라이브러리 로그, 업로드 임시 파일)
```

- status: `pending`(diff·매칭 준비 완료) → [번역 실행] → `translating` → `translated` / `failed`([재시도]). `pending`에서 [반려](사유 필수) → `rejected`. 기존 `auto_approved`·`approved` 상태는 없앤다.
- status.json: `id, title(기본 수정본 파일명), ext, status, created_at, uploaded_by, decided_at, decided_by, reason, error, files{original?, revised, base_zh-CN?, base_zh-TW?: 표시용 원래 파일명}, counts, alignment{lang: {total, matched}}, stats{lang: {segments, reused, translated}}, outputs{lang: path}`.
- 업로드 시 diff·매칭 생성까지 끝난 뒤 작업을 공개(임시 폴더 → 원자적 이동). 실패하면 아무것도 남기지 않고 400 + 안전한 진단 메시지.
- 원본과 수정본이 바이트 동일하면 거부(400). 모든 파일 확장자는 수정본과 같아야 함. 파일당 기본 50MB(`serve --max-upload-mb`), 요청 전체는 파일 수 × 한도 + 여유.
- [삭제]: `translating`이 아닌 작업은 삭제 가능(확인 대화상자). 작업 폴더 전체 삭제.
- 동시 번역은 지금처럼 파이프라인 잠금으로 직렬화해도 된다.

## 4. API

| 메서드·경로 | 동작 |
| --- | --- |
| `GET /api/jobs` | `JobSummary[]` 최신순 |
| `POST /api/jobs` (multipart) | 필드 `original?`, `revised`, `base_zh_cn?`, `base_zh_tw?`, `title?`, `by?`. 201 + `JobDetail` |
| `GET /api/jobs/{id}` | `JobDetail`(changes, alignment 상세, artifacts, outputs, stats) |
| `GET /api/jobs/{id}/sheets` / `slides` | 지금과 같은 형식 |
| `POST /api/jobs/{id}/translate` `{by?}` | pending → 202, 백그라운드 번역 |
| `POST /api/jobs/{id}/reject` `{reason, by?}` | 사유 비면 400 |
| `POST /api/jobs/{id}/retry` | failed → 202 |
| `DELETE /api/jobs/{id}` | translating이면 409 |
| `GET /api/jobs/{id}/files/{name}` | redline·출력 내려받기. 작업 폴더 밖 경로 차단 |

Host 허용(`--allowed-host`)·동일 출처 검사·보안 헤더·스트리밍 업로드 제한은 그대로 유지(업로드는 `app/web/uploads.py` 재사용·확장).

## 5. 화면

- `/` 작업 목록: 제목, 형식, 상태 배지, 변경 건수(추가/삭제/수정), 기존본 매칭(예: "간체 20/22 · 번체 없음"), 올린 사람, 생성 시각. 상태 필터·검색. 상단 [새 작업].
- `/new` 업로드 한 화면: 파일 칸 4개(원본, 수정본*, 기존 간체본, 기존 번체본). 각 칸에 선택된 파일명 표시, 형식 불일치는 즉시 안내. 제목(수정본 파일명으로 미리 채움), 올린 사람(localStorage). [올리기] → 상세로 이동. 업로드 중에는 진행 표시와 중복 제출 방지.
- `/jobs/:id` 상세: 머리(제목, 파일 4개 이름, 상태, 올린 사람). **diff**(기존 ChangeTable·InlineDiff·redline 내려받기·SheetDiff·SlideDiff 재사용; 원본 없으면 "신규 문서 — 전체 번역"). **번역 계획**: 언어별 "기존 번역 재사용 예정 N개 / 새로 번역 M개"(번역 기억과 수정본 세그먼트로 미리 계산) + 매칭 안 된 원본 문장 샘플 + 낮은 매칭률 경고. [번역 실행](확인 대화상자)·[반려]. 번역 중 2초 폴링, 완료 시 내려받기와 언어별 통계. failed면 오류와 [재시도]. [삭제].

## 6. 테스트

- 매칭: docx·pptx 위치 일치(우리 번역본), 사람이 중국어본에 문단을 추가/삭제한 경우 해당 부분만 미매칭, xlsx 셀 주소 매칭(추출 순서가 달라도), 수식 제외, 머리글·바닥글, 같은 원문에 다른 번역 → 최빈값, 형식 불일치 거부.
- 작업 흐름(FakeAgent): 기존본 있음 → 안 바뀐 문장 재사용·바뀐 문장만 번역(통계 확인), 기존본 없음 → 전체 번역, 원본 없음 → 신규 전체 번역, 언어 하나만 기존본.
- 업로드 거부(동일 파일, 확장자 불일치, 손상 파일, 크기 초과, 다른 Origin 403), 실패 시 잔여 파일 없음, 삭제, translating 중 삭제 409, 경로 탈출 차단.
- 프론트: 업로드 4칸 폼(필수·형식 불일치·제목 자동 채움·이동), 상세의 diff·번역 계획·경고·번역 실행·폴링·내려받기·삭제.
