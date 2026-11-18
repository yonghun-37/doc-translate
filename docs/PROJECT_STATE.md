# 프로젝트 현재 상태

## 개요와 현재 구조

한국어 Office 원본·수정본과 선택한 중국어 기존본을 함께 올려 검토하고 간체·번체 결과를 만드는 도구입니다. **업로드 1회 = 독립 작업(job)**이며 doc/rev 이력·번호·기준본 순서 제약은 제거했습니다. 기준은 [layout-view.md](specs/layout-view.md), [job-model.md](specs/job-model.md)와 [design.md](specs/design.md), 현재 구조는 [architecture.md](architecture.md), 작업 모델 구현 결과는 [job-implementation/result.md](specs/job-implementation/result.md), 이번 변경 결과는 [layout-implementation/result.md](specs/layout-implementation/result.md)입니다. 이전 구현 기록은 과거 구현 문서로 유지하며 web-upload.md는 대체 표시만 추가했습니다.

Python 3.12·FastAPI와 React SPA, docutranslate 추출/되쓰기/LLM, python-redlines DOCX 비교, daff XLSX 비교를 사용합니다. 데이터는 `jobs/<id>/{inputs,review,output}`와 status.json, 공통 logs입니다. 모든 inputs는 등록 후 불변이며 삭제는 작업 전체를 제거합니다. 저장 구조 결정은 [ADR-003](adr/ADR-003-independent-jobs-and-uploaded-memory.md), 외부 렌더링·상태 병합은 [ADR-004](adr/ADR-004-layout-preview-and-progress.md)에 기록했습니다.

## 구현된 기능

- 원래 모양/변경 목록 탭, 목록 위치에서 셀·페이지·슬라이드로 이동. SheetView 격자·스타일·병합·행/열 크기·시트 탭·삭제 행 펼치기·변경 이동, PageView 지연 로딩·썸네일·변경 수, SlideCompare 원본/수정본·도형 테두리·노트·변경 필터.
- XLSX는 daff의 행 정렬을 읽기 전용 셀 주소와 연결하고 머리글/바닥글 위치도 표시. 최대 2,000행 × 100열에서 변경 주변을 우선 포함하며 선택 위치 query로 범위를 다시 불러옴. PPT는 제목/본문/표/노트 위치와 바깥 그룹 기준 도형 좌표.
- LibreOffice → PDFium 5.15.2 PNG 렌더러, Word 순차 페이지 매핑. 업로드 응답 후 실행·독립 프로필·120초 제한·프로세스 그룹 종료·직렬 렌더 잠금, 문서당 기본 300페이지·긴 변 1600px. preview unavailable/failed는 번역을 차단하지 않음. **실제 LibreOffice 통합 성공은 아직 확인하지 못함.**
- `[render] soffice/timeout_sec/max_pages`, 환경변수 DOC_TRANSLATE_SOFFICE 우선. `[translator.openai_compatible] progress_batch=40` 묶음 콜백, 숫자만 포함한 최근 50개 기록·ETA·언어별 진행과 2초 폴링. 중간 진행은 초당 최대 1회, 완료/실패는 즉시 저장.
- 짧은 상태 잠금으로 미리보기·번역 진행 필드를 병합하고 삭제와 공개를 보호. 미리보기 PNG/overlays API의 경로·심볼릭 링크 차단, CSP `img-src 'self'` 유지.

- `/new` 네 파일 업로드: 수정본 필수, 원본·기존 간체본·기존 번체본 선택. 파일명 자유, 제목·올린 사람, 동일 확장자/ZIP CRC/필수 파트/XML 검증. 원본·수정본 동일 바이트 거부.
- 기존 multipart 파서 확장: 파일별 기본 50MB, 요청 최대 4배+64KiB. 초과 즉시 수신 중단, 실패·연결 중단 정리. diff·매칭·기억·계획·상태 준비 후 job 폴더 전체 원자적 공개.
- DOCX·PPTX 위치 키 그룹 SequenceMatcher와 그룹 크기 검사, XLSX 읽기 전용 시트·셀 주소/머리글·바닥글 매칭. 동일 원문은 최빈값·동률 첫 후보. 빈/원문 동일 번역 제외. 언어별 매칭 수·최대 20개 미매칭 샘플.
- 수정본과 기억으로 언어별 재사용 예정·새 번역 계획, 낮은 매칭률 경고. 원본 없는 신규·기존본 없는 언어는 전체 번역.
- `/api/jobs`, `/`, `/new`, `/jobs/:id`: 최신순 목록·검색/상태 필터·메타데이터·기존 변경 표·문자/시트/슬라이드 비교·redline 다운로드.
- `pending → translating → translated | failed`, `pending → rejected`, 실패 재시도. 번역 실행 확인·사유 필수 반려·2초 폴링. 두 언어 모두 성공 후 다운로드와 언어별 통계. translating 외 작업 삭제 확인·삭제 중 충돌 409.
- 기존 엔진·ReuseAgent/FakeAgent·비교·위치 컴포넌트 재사용. 정확한 문자열 재사용·누락 원문 중복 제거·숫자/단위 제외. XLSX 출력은 ZIP의 headerFooter 해당 XML만 보완하고 openpyxl로 저장하지 않음.
- 본문·표·머리글/바닥글·각주/미주·텍스트 상자·발표자 노트·마스터/레이아웃 처리, 메모·시트명·수식 제외. 이미지/미디어 보존 회귀 테스트 유지.
- serve·check-translator와 `--root`, `--config`, `--allowed-host`, `--max-upload-mb` 유지. 이전 CLI/API·루트 데이터 폴더 제거. 빈 데이터 전제이므로 이전 코드 없음.
- Host·동일 출처(POST·DELETE 포함)·보안 헤더·다운로드 경로/심볼릭 링크 차단. 원자적 상태 저장·직렬 flock·안전한 오류/이벤트·라이브러리 로그 유지.
- 기존 LLM allowed_hosts·CA·프록시/TLS 검증·키·용어집 설정 유지. config.toml 자동 수정 없음. json_mode=false 기본이며 사용자 제공 HiveAI 실측(2026-11-17, 비활성화 후 12/12 성공)은 이전 근거로 유지하고 재시험하지 않음.

## 검증 상태

- `.venv/bin/python -m pytest -q`: **179개 통과, 실제 LibreOffice 통합 2개 skip**. 가짜 PDF·FakeAgent를 사용하며 환경변수 미지정 시 통합만 skip합니다.
- `cd frontend && npm test && npm run typecheck && npm run build`: **34개 테스트 통과·타입 검사·운영 빌드 성공**.
- 실제 LibreOffice를 지정한 전체 실행은 **179개 통과, 통합 2개 실패**였습니다. 실행 파일의 버전은 26.2.7.3이며 직접 PDF 변환도 출력 없이 종료 코드 1을 반환했습니다. 이 샌드박스에서는 AF_UNIX/AF_INET 소켓 작업이 EPERM입니다. 실제 변환 실패의 직접 내부 원인은 확인하지 못했으며 일반 로컬 실행 환경에서 재검증해야 합니다. 테스트를 우회/자동 skip하지 않았습니다.
- 실제 브라우저 시작도 Chromium `sandbox_host_linux.cc`의 `shutdown: Operation not permitted`로 실패했습니다. 페이지의 실물 렌더링·브라우저 시각 확인은 미완료입니다.
- 기존 매칭·서식·미디어·출력 불변·Host/Origin·업로드·경로 보안 회귀를 유지합니다. 새 검증은 주소/행 삽입·격자 제한·순차 페이지·묶음/ETA/로그/저장 빈도·가짜 PDF·시간 초과·삭제/번역 경합·미리보기 API와 화면 이동을 포함합니다.
- 실제 LLM 호출·네트워크 사용·패키지 설치·Git 커밋은 하지 않았습니다. config.toml과 잠금/npm manifest, 사용자가 미리 반영한 pyproject.toml 변경을 보존합니다.

## 구현 판단과 명세 구체화

- layout-view.md 8절에 실제 JSON 필드·격자 위치 query·진행 수치 의미를 구체화했습니다. 한 화면의 한도보다 변경 위치가 많을 때 전부 동시에 포함할 수 없어 위치 선택 시 해당 범위를 우선 표시합니다. 중간 진행 쓰기는 초당 1회로 제한하되 최종 상태/기록은 유실을 막기 위해 즉시 저장합니다.

- 작업별 계획을 `review/plan.json`에 추가했습니다. 조회 때 Office를 다시 추출하지 않고 사용자가 확인한 계획을 보존하기 위한 구현 세부사항입니다. 상세 API의 `plan`은 언어별 통계와 같은 형식입니다.
- reused 통계는 **업로드한 기존 기억**의 적중만 셉니다. 같은 실행 안에서 새로 번역한 문장의 캐시 중복은 제외하여 계획과 실제 통계를 일치시켰습니다. 새 번역은 고유 문장 수, segments는 전체 세그먼트 수입니다.
- 원본 없이 중국어본을 올리는 것은 허용하지만 그 언어의 매칭은 0/0이고 재사용은 0입니다. 기존본 없는 언어는 alignment에서 생략합니다. 모든 입력은 손상 검증합니다.
- XLSX 추출 경로가 workbook.xml을 읽지 않아 손상 파일을 놓치는 회귀 테스트를 확인한 후 ZIP 내부 XML 문법 검증을 보완했습니다. 라이브러리는 수정하지 않았습니다.
- 파일명은 UTF-8 240바이트, 제목은 240자·이름은 200자로 제한합니다. 출력 이름 접미사·파일시스템 한도와 메타데이터 크기를 고려한 경계입니다. 입력 원래 경로는 제거하고 파일명만 표시합니다.
- 현재 uv.lock에는 python-multipart==0.0.34 직접 의존성이 이미 반영되어 있음을 확인했습니다. 이전 문서의 잠금 갱신 필요 안내를 수정했고 잠금 파일 자체는 변경하지 않았습니다.

## 알려진 한계와 제약

- **위치 매칭의 의미 한계:** 명세의 위치 키 알고리즘을 그대로 사용합니다. DOCX 본문에 문단을 삽입/삭제해 뒤쪽 번호가 바뀌면 동일 키·개수여도 잘못 매칭할 수 있습니다. 위치 키가 유지되는 그룹의 세그먼트 수 변경은 해당 그룹만 제외합니다. XLSX도 시트명/순서·셀 주소가 함께 바뀌면 대응이 정확하지 않을 수 있습니다. 높은 매칭률이 번역 정확도를 보장하지 않습니다.
- 같은 원문은 위치/문맥에 관계없이 한 번역을 재사용합니다. 기존 기억은 용어집·모델을 바꿔도 자동 갱신하지 않습니다. XLSX total은 고유 셀 텍스트 추출+머리글/바닥글 세그먼트이며 셀 개수와 다릅니다.
- **문단 내 부분 서식:** docutranslate가 굵게·기울임·글자색만 다른 run을 합칠 수 있어 첫 run 서식을 따릅니다. 번역 길이로 인한 줄바꿈·페이지 배치 변화도 가능하며 Office 화면의 동일 배치를 보장하지 않습니다.
- XLSX 변경 목록은 daff 행 대응 기준 실제 셀입니다. 격자는 수식 캐시 결과 또는 수식 문자열을 표시하며, 모든 사용자 지정 숫자 서식·조건부 서식·차트·도형은 재현하지 않습니다. PPTX 공통 diff에는 마스터/레이아웃이 포함되고 슬라이드 표는 실제 슬라이드·노트 기준입니다. 복잡한 중첩 구조 위치는 순번으로 남을 수 있습니다.
- Word 페이지는 redline PDF의 순차 텍스트 탐색 결과이며 문단이 여러 페이지에 걸치거나 글자 추출/추적 변경 표현이 다르면 기존 위치로 남습니다. 서버 글꼴·LibreOffice 조판은 실제 Word/PPT와 다를 수 있습니다. 미리보기 page 한도 초과·마스터/레이아웃 변경은 목록에서 확인합니다.
- 매우 긴 문단의 InlineDiff는 공통 앞뒤를 제외한 길이 곱 1,000,000 초과 시 중간 전체를 삭제/추가로 강조합니다.
- Linux 단일 서비스·직렬 파이프라인입니다. 긴 번역 중 다른 변경 요청이 기다릴 수 있으며 로그인·영속 큐·다중 작업자·취소는 없습니다.
- 크기 한도는 압축 파일 바이트 기준이며 ZIP 해제 크기·문서 복잡도 제한은 별도로 없습니다. Starlette 내부 상태를 쓰는 multipart 서브클래스는 의존성 갱신 시 스트리밍/정리 테스트가 필요합니다.
- **강제 종료 복구:** 등록 중 SIGKILL·정전에는 logs/.uploads 임시 폴더가 남을 수 있습니다. 번역 중이면 translating 상태·`.work-*`·상태 공개 전 output이 남을 수 있습니다. 모든 서비스 프로세스를 중지한 뒤 임시/부분 출력을 정리하고 해당 status를 failed, outputs={}, stats={}로 복구해 재시도합니다. inputs·review 기억은 수정하지 않습니다. 일반 번역 예외·Ctrl+C에는 자동 실패 정리를 합니다. 렌더링 중 강제 종료는 preview pending과 logs/.render-*·.lo-profile 잔여물을 남길 수 있으며, 자동 재개 없이 서비스 중지·정리 후 새 작업으로 다시 올립니다.
- jobs와 logs는 같은 파일시스템이어야 등록 폴더를 원자적으로 이동할 수 있습니다. 입력·검토·기억은 업무 데이터를 포함하며 서비스 파일 권한과 인증 프록시는 운영 환경에서 관리합니다.
- 샌드박스의 asyncio 로컬 wakeup 제한은 TestClient의 주기 타이머로만 보완합니다. 서버에는 테스트 우회 코드를 넣지 않았습니다.

## 진행 중과 다음 확인

레이아웃·진행 표시 코드와 오프라인 검증을 구현했습니다. **완료 조건 중 실제 LibreOffice 통합 성공과 수동 화면 확인이 남아 있습니다.** 소켓/프로세스 제한이 없는 일반 개발 셸에서 DOC_TRANSLATE_SOFFICE를 지정한 전체 pytest와 Word/PPT 미리보기·브라우저 확인을 수행해야 합니다. 실제 LLM 연결은 사용자가 check-translator를 명시적으로 실행할 때만 확인합니다. 인증 프록시·systemd·Office 배치와 번역 품질은 운영 배포 시 별도 확인 대상입니다.
