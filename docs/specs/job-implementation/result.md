# 작업 단위 모델 구현 결과

기준: [job-model.md](../job-model.md). doc/rev 기반 저장·입력·상태·API를 독립 job으로 전환했습니다. [ADR-003](../../adr/ADR-003-independent-jobs-and-uploaded-memory.md)에 구조 변경 이유를 기록했습니다.

## 구현

- 수정본 필수·원본/간체/번체 선택 네 파일 업로드, 동일 형식/동일 바이트/손상/크기 검증, 임시 job 준비 후 폴더 전체 원자적 공개.
- DOCX·PPTX 위치 키 그룹 정렬과 개수 검사, XLSX 읽기 전용 셀 주소·시트 대응 및 기존 머리글/바닥글 경로로 매칭. 최빈값·동률 첫 후보, 빈/동일 번역 제외.
- 언어별 기억·매칭 요약/샘플·수정본 번역 계획. 기존본 없는 언어·원본 없는 신규는 전체 번역.
- job API와 불변 inputs, pending/ translating/ translated/ failed/ rejected 상태, 명시적 실행·반려·재시도·삭제. 두 언어 성공 후 출력 공개, 실패 시 부분 출력 정리.
- 기존 React 목록·업로드·상세·비교/결정/결과 컴포넌트 재사용. 최신순·필터/검색, 네 파일 폼, 계획·낮은 매칭률 경고·샘플, 2초 폴링·다운로드·언어별 통계·삭제 확인.
- serve의 allowed-host/max-upload-mb, check-translator, Host/Origin/보안 헤더 유지. DELETE 동일 출처 검사와 translating 삭제 409, job별 파일 허용 목록·경로/심볼릭 링크 차단.

## 바꾼 파일

| 영역 | 파일과 변경 |
| --- | --- |
| 저장·흐름 | `app/storage.py`, `pipeline.py`: job ID·원자적 공개·상태·번역·삭제. `inputs.py`: 자유 파일명/ZIP/XML 검증. `cli.py`: serve·check-translator만 유지. `diagnostics.py`: 폐기된 rev 진단 제거 |
| 매칭·재사용 | 새 `app/alignment.py`, `app/reuse_agent.py`, `app/xlsx_headers.py`: 위치/셀 매칭·최빈값 기억·계획·언어별 통계, 머리글/바닥글 공통 추출/토큰화 |
| 웹 | `app/web/__init__.py`, `models.py`, `uploads.py`: job API/응답 모델·네 파일 스트리밍·보안·안전한 다운로드 |
| 화면 | `frontend/src/App.tsx`, `api.ts`, `pages/ReviewList.tsx`, `ReviewDetail.tsx`, `Upload.tsx`, `components/DecisionPanel.tsx`, `OutputFiles.tsx`, `StatusBadge.tsx`, 새 `TranslationPlan.tsx`, `styles.css` |
| 테스트 | 새 `tests/test_alignment.py`, 전환한 `test_pipeline.py`, `test_uploads.py`, `test_web_cli.py`, `test_core.py`, `test_diagnostics_locations.py`; `frontend/src/test/App.test.tsx`, `Upload.test.tsx` |
| 데이터·운영 | `.gitignore`, `jobs/.gitkeep`, `deploy/doc-translate.service`; 비어 있던 inbox/versions/review/output의 `.gitkeep`와 폴더 제거 |
| 문서 | `AGENTS.md`, `README.md`, `docs/specs/design.md`, `frontend-react.md`, `deployment-intranet.md`, `docs/PROJECT_STATE.md`, `docs/architecture.md`, 새 ADR-003, 이 디렉토리의 plan/result. `web-upload.md`는 상단 대체 표시만 추가 |

`app/engine.py`, `app/locations.py`, `app/diff/*`, FakeAgent와 기존 비교 컴포넌트는 재사용했습니다. 라이브러리 소스는 복사·수정하지 않았고 openpyxl은 매칭에서 읽기 전용으로만 사용합니다. XLSX 출력 보완은 기존 ZIP XML 교체 경로입니다.

## 명세와 다른 점·구체화와 이유

1. 저장 트리에 `review/plan.json`을 추가했습니다. 상세 API는 `plan{lang: {segments,reused,translated}}`을 제공합니다. 명세의 사전 번역 계획을 업로드 시 계산해 보존하고, 조회 때 Office 추출을 반복하지 않기 위한 저장 방식입니다.
2. 예전 ReuseAgent는 같은 실행 중 새로 채운 캐시도 reused에 셌지만, 현재는 업로드에서 얻은 기존 기억 적중만 셉니다. 새 번역 문장의 중복은 translated에서 중복 제거하고 reused에는 넣지 않습니다. 계획과 실제의 의미를 맞췄으며 세 형식/언어별 테스트에서 일치를 확인했습니다.
3. 원본 없이 기존본을 올려도 거부하지 않습니다. 모든 파일을 검증하되 해당 매칭은 0/0, 재사용 0으로 표시하고 전체 번역합니다. 기존본 없는 언어는 alignment 항목을 생략합니다.
4. 요청 총량은 최대 파일 수인 4개 기준 `4 × 파일 한도 + 64KiB`, 파일은 개별 한도, 텍스트 필드는 최대 2개·각 16KiB입니다. 제목 240자·이름 200자·표시 파일명 UTF-8 240바이트로 경계를 구체화했습니다. 출력 접미사와 파일시스템 이름 길이도 고려했습니다.
5. 입력 ZIP의 CRC·필수 파트 외 내부 XML 문법까지 검사합니다. XLSX upstream 추출이 workbook.xml을 읽지 않아 손상된 파일을 신규/기존본 역할에서 받아들이는 문제를 보강 테스트로 발견해 수정했습니다.
6. doc/rev 전용 status CLI도 제거했습니다. 작업 목록은 웹/API로 제공하며 실행 CLI는 serve·check-translator 두 개입니다. 마이그레이션·과거 상태 호환은 추가하지 않았습니다.

`job-model.md` 원문은 수정하지 않았습니다. 위 구현 세부사항은 design.md·frontend-react.md·PROJECT_STATE에 반영했습니다. 기존 uv.lock을 읽어 python-multipart 직접 의존성이 이미 반영된 것을 확인했으므로, 과거 배포 문서의 잠금 갱신 필요 안내만 바로잡았습니다.

## 검증

- `.venv/bin/python -m pytest -q`: **163 passed (28.82초)**.
- `cd frontend && npm test && npm run typecheck && npm run build`: **25 tests passed**, TypeScript 검사 및 Vite 운영 빌드 성공.
- 기존 엔진·서식/미디어 보존·비교·설정/TLS·로그 비밀정보 차단 테스트 유지.
- 생성 번역본 매칭, 수동 문단 추가/삭제로 같은 위치 그룹의 개수가 달라진 경우 해당 그룹 제외, 위치 키 누락/추가 정렬, XLSX 추출 순서와 무관한 주소 대응·수식 제외·시트명/순서 대응·머리글/바닥글·중복 원문 투표·샘플 제한 검증.
- 세 형식 × 양쪽 기존본/한쪽만/기존본 없음/원본 없음의 FakeAgent 흐름에서 호출 문장·언어별 계획/실행 통계·입력/검토 기억 불변 검증.
- 실제 redline/시트/슬라이드 산출물, 등록 준비·이동 실패의 미공개/정리, 연결 중단·한도 수신 중단·네 파일 개별 한도, 손상 XML 역할별 거부, 번역 실패·Ctrl+C·재시도, 동시 독립 작업·번역 중 삭제 즉시 거부, 잘못된 상태 전이·파일 접근·Origin·프록시 Host 검증.
- SHA-256으로 `config.toml`, `uv.lock`, `frontend/package.json`, `frontend/package-lock.json`, `pyproject.toml`이 시작 시와 동일함을 확인. job-model.md 동일, web-upload.md 상단 표시 외 동일함도 확인.
- Git ignore 검사에서 jobs/logs 내용물은 제외하고 `.gitkeep`는 제외하지 않음을 확인. 기존 저장소는 커밋 없는 미추적 파일 상태였으며 관련 없는 파일을 보존했습니다.
- 패키지 설치·추가, 네트워크 요청, 실제 LLM API 호출, Git 커밋·푸시, 서비스 설치·실행 없음.

## 남은 한계

- 명세의 위치 키 매칭은 의미 정렬이 아닙니다. DOCX 본문 중간 문단 삽입/삭제로 후속 번호가 바뀌는 경우, 같은 키·개수에 잘못 매칭할 수 있습니다. 테스트는 위치 키가 유지되는 그룹 내 문단 추가/삭제의 부분 제외를 검증하며 임의의 수동 편집 복구를 보장하지 않습니다. XLSX도 시트명/순서·주소 변경의 의미는 추론하지 않습니다. 높은 매칭률은 번역 품질 보장이 아닙니다.
- 문단 내부 run 서식 병합·번역 길이에 따른 Office 배치 변화는 기존 docutranslate 한계입니다. 실제 브라우저 시각 검토·Office 렌더링·사내 API·systemd는 배포 환경에서 확인해야 합니다.
- 단일 직렬 잠금·BackgroundTasks이며 영속 큐·자동 강제 종료 복구는 없습니다. SIGKILL/정전의 임시 폴더/상태/부분 출력 정리 절차는 PROJECT_STATE에 기록했습니다. jobs·logs는 같은 파일시스템에 있어야 합니다.
- 업로드 한도는 압축 바이트 기준이며 ZIP 해제 크기·문서 복잡도는 별도로 제한하지 않습니다.

요청된 작업 모델 구현과 오프라인 완료 조건은 충족했습니다. 실제 운영 환경 확인 외 미완료 구현 항목은 없습니다.
