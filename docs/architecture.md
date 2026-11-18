# 현재 구조

현재 단위는 독립 작업(job)입니다. [job-model.md](specs/job-model.md)가 입력·상태 규칙을 정의합니다. 라이브러리·React·연결 보안 경계는 [ADR-001](adr/ADR-001-react-and-intranet-boundaries.md), 기존 웹 업로드 전환은 [ADR-002](adr/ADR-002-web-upload-and-explicit-translation.md), doc/rev를 대체한 현재 결정은 [ADR-003](adr/ADR-003-independent-jobs-and-uploaded-memory.md), 미리보기·진행 저장은 [ADR-004](adr/ADR-004-layout-preview-and-progress.md)에 기록합니다.

## 구성과 흐름

```text
React /new → POST /api/jobs → 스트리밍 임시 수신
  → 입력 검증/추출 → 원본↔수정본 diff + 언어별 기존본 매칭/기억/계획
  → job 폴더 원자적 공개 (pending)
  → 업로드 응답 후 미리보기 BackgroundTasks → LibreOffice PDF → PDFium PNG/페이지 위치
React /jobs/:id → 번역 실행 → translating 예약 → BackgroundTasks
  → ReuseAgent + docutranslate → 두 언어 output 공개 → translated
```

- `app/cli.py`: serve·check-translator. `--root`, `--config`, `--allowed-host`, `--max-upload-mb` 유지.
- `app/storage.py`, `app/inputs.py`: job ID·안전한 경로·파일명·ZIP 검증, 원자적 JSON 저장, 최신순 상태 목록.
- `app/render.py`, `app/slide_layout.py`: LibreOffice 독립 프로필·시간 제한·직렬 변환, PDFium PNG·텍스트, 순차 Word 페이지 위치와 PPT 도형 좌표.
- `app/grid.py`: 읽기 전용 XLSX 격자·서식·병합·실제 셀 주소와 daff 행 대응, 표시 한도·선택 위치.
- `app/progress.py`: 묶음별 수치·단계·ETA·최근 50개 기록. ReuseAgent의 progress_batch 기본 40.
- `app/pipeline.py`: 작업 준비/공개, 상태 전이·삭제, 직렬 번역·실패 정리.
- `app/alignment.py`: DOCX/PPTX 위치 그룹 SequenceMatcher, XLSX 읽기 전용 셀 주소·시트 대응. 최빈값 기억, 미매칭 샘플, 수정본 기준 계획.
- `app/engine.py`, `app/locations.py`: 기존 docutranslate 추출·되쓰기와 사람이 읽을 위치. DOCX 각주/미주는 StoryPart 연결 서브클래스, XLSX 추출은 identity FakeAgent 경로.
- `app/reuse_agent.py`: 완전 일치 기억 재사용·누락 원문 중복 제거·숫자/단위 제외·부분 실패 차단.
- `app/xlsx_headers.py`: 공통 토큰화로 headerFooter 추출·번역. 출력 ZIP의 해당 worksheet XML만 교체.
- `app/diff/`: 공통 세그먼트 비교, python-redlines/Docxodus 변경 추적, daff 시트 JSON, PPTX 도형·노트 비교.
- `app/config.py`, `app/secure_agent.py`: 기존 설정/키/용어집/호스트 허용/TLS 검증/프록시. HTTP 요청·묶음 내부 병렬화·재시도는 upstream 위임. 앱 진행 묶음은 progress_batch, 외부 렌더링은 [render]에서 설정.
- `app/diagnostics.py`: 원문·키 없는 고정 진단과 라이브러리 경고/오류 로그.
- `app/web/uploads.py`: Starlette multipart 서브클래스, 파일별/요청 전체 스트리밍 제한·임시 파일 정리.
- `app/web/`: job API·Pydantic 모델·안전한 다운로드·SPA 정적 서빙.
- `frontend/`: Vite·React·TypeScript·React Query·Router, 기존 비교 컴포넌트와 번역 계획 화면, 직접 작성 CSS. HTML 삽입 없음.

## 저장·상태·동시성

`jobs/<id>` 안에 status.json, inputs, review, output을 둡니다. ID는 UTC 시각+무작위 6자리이며 경로 성분을 검증합니다. 파일명은 표시 정보이고 inputs 파일명은 역할별 고정 이름입니다. 등록 후 모든 inputs·검토 기억은 불변입니다. 다른 작업 상태·메모리에 의존하지 않습니다. 삭제는 작업 전체를 제거합니다. 이전 데이터/호환 API는 없습니다.

업로드 수신과 job 준비는 logs/.uploads의 임시 공간에서 수행합니다. 추출·diff·매칭·기억·계획·상태 준비 후 폴더 전체를 jobs로 원자적 이동합니다. jobs·logs는 같은 파일시스템에 둡니다. 실패·연결 중단에는 임시 파일을 정리하고 job을 공개하지 않습니다.

`pending → translating → translated | failed`, `pending → rejected`, `failed → translating`입니다. approved·auto_approved 상태는 없습니다. 번역 출력은 job 임시 폴더에서 두 언어를 모두 준비한 뒤 output 디렉토리를 이동하고 translated 상태를 기록합니다. 일반 예외·Ctrl+C는 부분 출력 정리·failed 전환을 수행합니다. SIGKILL/정전 후 영속 큐·자동 재개는 없으며 운영자가 중지 후 복구합니다.

동일 root의 Pipeline은 logs/.pipeline.lock의 flock으로 상태 변경·번역을 직렬화합니다. translating 삭제는 잠금 대기 전과 잠금 안에서 검사합니다. 읽기는 원자적 상태 스냅샷을 사용합니다. 미리보기 공개·상태 필드 병합·삭제는 짧은 logs/.status.lock을 공유합니다. 렌더러는 .pipeline.lock을 잡지 않아 번역과 겹칠 수 있으며 최신 상태의 preview만 갱신합니다. logs/.render.lock과 프로세스 스레드 잠금은 렌더링을 직렬화합니다. 목록 10초, translating 상세 2초, preview pending 상세 3초 폴링입니다. 업로드 시 계산한 계획을 review/plan.json에 저장해 조회 시 Office 재추출을 피합니다.

## 배포·보안 경계

FastAPI는 127.0.0.1 전용, 인증은 별도 프록시에서 수행합니다. 허용 Host·동일 출처(POST·DELETE 포함)·보안 헤더·요청 크기 한도를 적용합니다. 다운로드는 job별 redline.docx, ready 미리보기의 PNG/overlays.json과 translated 상태의 출력 이름 목록만 허용하고 폴더 탈출·심볼릭 링크를 차단합니다. 입력·기억·상태 파일은 다운로드하지 않습니다.

운영은 frontend/dist와 Python 소스를 함께 배포하며 정적 파일 위치는 데이터 root와 독립적입니다. jobs·logs만 서비스 쓰기 데이터이며 Git에서 내용물을 제외합니다. 설치 의존성과 잠금 파일은 이번 구현에서 변경하지 않습니다. 현재 uv.lock에는 python-multipart와 pypdfium2 5.15.2 직접 의존성이 반영되어 있습니다. LibreOffice는 서버 별도 설치이며 저장소에 포함하지 않습니다.

키 조회 전 LLM 호스트 정책을 검증합니다. TLS는 SSLContext로 검증하며 리디렉션을 따르지 않고 환경 프록시는 선택 사항입니다. 원문/키/응답 본문/예외 상세는 로그에 남기지 않습니다. 실제 연결은 명시적 번역 실행이나 check-translator에서만 사용합니다.

미리보기 상태는 작업 상태와 별도입니다. `preview={status,message,pages}`이며 unavailable/failed에서도 pending 작업을 번역할 수 있습니다. 작업의 review/preview에 페이지 PNG·PPT overlays.json, Word의 review/redline.pdf를 보관합니다. 입력과 기억은 계속 불변이며 changes.json의 Word page/where만 미리보기 완료 시 원자적으로 보완합니다.

번역 progress는 status.json에 언어별 수치·단계·시각·ETA·최근 50개 숫자 기록으로 저장합니다. 중간 스냅샷은 초당 최대 1회, 완료/실패 상태는 마지막 기록과 함께 즉시 저장합니다. 실제 LLM 요청 없이 가짜 PDF와 FakeAgent로 테스트하며, 실제 LibreOffice 통합은 DOC_TRANSLATE_SOFFICE가 있을 때만 실행합니다.
