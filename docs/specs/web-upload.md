> **job-model.md로 대체됨** — 현재 작업·업로드·상태 규칙은 [job-model.md](job-model.md)를 따릅니다. 아래는 이전 명세입니다.

# 웹 업로드와 번역 실행 버튼

2026-11-17 사용자 결정: 실제 운영에서는 사용자가 웹에서 문서를 직접 올리고, 버튼을 눌러 번역을 실행합니다. 이 문서는 `design.md`·`frontend-react.md`의 입력·상태 규칙 중 아래 항목을 대체합니다.

## 1. 결정

| 항목 | 결정 |
| --- | --- |
| 입력 | 웹 업로드가 기본 입구. inbox 감시(`watch` 명령, `deploy/doc-translate-watch.service`)는 제거. `process` CLI는 관리자 일괄 등록용으로 남김(파일명 규칙 `문서명_rev001.docx` 유지) |
| 신규 여부 | 업로드 화면의 **"신규 문서" 체크박스**로 사용자가 지정 |
| rev 번호 | 시스템이 부여. 신규 → rev001. 기존 문서 → 그 문서의 가장 큰 rev + 1(반려된 rev도 번호를 소비). 업로드 파일명은 자유 |
| 번역 시작 | 자동 번역 없음. **rev001도** `pending`으로 등록되고 사용자가 [번역 실행]을 눌러야 번역. rev002+는 변경 검토 후 [승인 후 번역] |
| 형식·크기 | docx·xlsx·pptx만. 기본 50MB(`serve --max-upload-mb`) |

## 2. 상태 규칙

- rev001: `pending`(base_rev=null, 변경 없음 대신 "신규 문서 — 전체 번역" 안내). 승인(=번역 실행) → `translating` → `translated`. 반려 가능(사유 필수).
- 기존 `auto_approved` 상태는 과거 데이터 표시용으로만 유지하고 새로 만들지 않음.
- 기존 문서에 새 판 업로드 거부 조건(409, 한국어 사유):
  - 그 문서에 `pending`·`approved`·`translating`·`failed` 상태 rev가 있음("rev002가 아직 처리 중입니다" 등).
  - 번역 완료된 rev가 하나도 없음(기준본 없음).
  - 확장자가 기존 문서와 다름.
  - 내용이 기준본(최신 translated rev)과 바이트 동일.
- 신규 업로드 거부: 같은 문서명이 이미 있음(409), 문서명이 `safe_doc` 규칙 위반(400).
- 업로드 파일 검증: 확장자, `validate_package`, 크기 초과 413. 실패 시 저장소에 아무것도 남기지 않음.
- 등록 기록: status.json에 `uploaded_by`(선택, 공백이면 null), 원본 파일명 `source_name`(표시용, 경로 성분 제거).
- 업로드와 `process`는 같은 등록 함수(Pipeline의 등록 경로)를 거쳐 잠금·원본 보관·diff 생성 규칙을 공유. 업로드는 inbox를 거치지 않고 `logs/.uploads/` 임시 파일 → 검증 → `versions/`로 이동.

## 3. API

| 메서드·경로 | 동작 |
| --- | --- |
| `GET /api/documents` | `DocumentSummary[]`: `{doc, ext, latest_rev, translated_rev: number|null, next_rev, blocked: string|null}` — 업로드 화면의 기존 문서 선택용. blocked는 거부 사유(없으면 null) |
| `POST /api/uploads` (multipart) | 필드: `file`, `new_doc`("true"/"false"), `doc`(신규면 필수, 기존이면 선택한 문서명), `by`(선택). 201 + `ReviewDetail`. 오류 400/409/413 `{detail}` |
| `POST /api/reviews/{doc}/{rev}/approve` | rev001 pending에도 동일하게 동작(번역 실행) |

- 업로드 본문은 스트리밍으로 받아 한도 초과 즉시 중단. 동일 출처 검사(기존 미들웨어)는 업로드에도 적용.
- `python-multipart`는 이미 설치된 전이 의존성이므로 `pyproject.toml`에 직접 의존성으로 명시만 하고 새 패키지를 추가하지 않음.

## 4. 화면

- 목록 상단에 [문서 올리기] 버튼 → `/upload`.
- `/upload`:
  - 파일 선택(accept=.docx,.xlsx,.pptx), "신규 문서" 체크박스, 올린 사람 이름(선택, 승인자 이름과 같은 localStorage 값 공유).
  - 신규 체크: 문서명 입력칸(파일명에서 확장자·`_revNNN` 제거한 값으로 미리 채움). "rev001로 등록됩니다".
  - 미체크: 기존 문서 선택 목록(같은 확장자만 활성, blocked 문서는 사유와 함께 비활성). "rev003으로 등록됩니다" 미리보기.
  - [올리기] → 성공 시 상세 화면으로 이동. 오류는 상단 배너.
- 상세: rev001 pending이면 변경 표 대신 "신규 문서입니다. 번역 실행 시 전체를 번역합니다." + [번역 실행](확인 대화상자) + [반려]. rev002+는 기존처럼 [승인 후 번역]·[반려]. 올린 사람·원본 파일명 표시.

## 5. 테스트

- 백엔드: 신규 업로드→rev001 pending→승인→translated(fake), 기존 문서 업로드→다음 rev·diff 생성, 각 거부 조건(중복 이름, 처리 중 rev, 기준본 없음, 확장자 불일치, 동일 내용, 손상 파일, 크기 초과, 다른 Origin 403), 실패 시 잔여 파일 없음, `/api/documents`의 next_rev·blocked.
- `process` CLI: rev001이 pending으로 등록되고 자동 번역하지 않음.
- 프론트: 업로드 폼(신규 체크 시 문서명 입력, 미체크 시 문서 선택과 rev 미리보기, blocked 비활성, 성공 시 이동), rev001 상세의 [번역 실행].
