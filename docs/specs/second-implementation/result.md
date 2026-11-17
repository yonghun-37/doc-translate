# 2차 구현 결과

> 이전 구현의 기록입니다. 현재 입력은 [웹 업로드](../web-upload.md)로 전환했으며 감시·신규 자동 번역은 제거했습니다. 최신 상태는 [업로드 구현 결과](../upload-implementation/result.md)를 참고하세요.

## 구현 내용

- Jinja2 화면·정적 CSS/JS 제거, FastAPI `/api/*`와 Pydantic 모델, Vite·React·TypeScript SPA로 교체했습니다. 조회·필터·문자 비교·형식별 검토·결정·폴링·내려받기를 구현했습니다. 운영은 앱 소스 옆 frontend/dist를 서빙합니다.
- daff hilite를 sheets.json 행으로 저장합니다. 셀의 `->` 때문에 달라지는 `-->` 등 구분자도 처리합니다. 기존 sheets.html 검토는 불변 원본에서 JSON을 계산해 조회합니다. React에 HTML 문자열을 삽입하지 않습니다.
- allowed_hosts·CA·프록시 설정과 레거시 원격 허용 경고를 추가했습니다. config.toml은 자동 수정하지 않으며 사내/HiveAI 예시를 분리했습니다. CLI --config·retry와 연결 확인의 소요 시간·추론 토큰 출력을 추가했습니다.
- 상태와 이벤트에 예외 종류·안전한 원인 요약을 남깁니다. HTTP 오류의 중첩 원인에서도 네트워크 분류를 보존하고 upstream fallback 실패의 HTTP 원인을 연결합니다. library.log는 경고/오류의 시각·레벨·고정 요약만 저장합니다.
- docutranslate 추출 요소로 DOCX 문단·표 셀·머리글/바닥글·노트/텍스트 상자와 PPTX 슬라이드·노트·마스터·레이아웃 위치를 표시합니다. 위치 정보가 없으면 세그먼트 순번을 유지합니다.
- html2text 설치 제외 override, systemd serve/watch 예시, 잠금 의존성 목록 스크립트와 설치 메타데이터 기반 THIRD_PARTY_LICENSES.md 생성기를 추가했습니다. MPL-2.0의 docutranslate·certifi·lightningcss는 수정 없이 사용합니다.

## 검증

- 시작 시 pytest **80 passed**를 확인했습니다.
- 최종 `.venv/bin/python -m pytest -q`: **109 passed**, 실패 0. html2text 제거 및 import 불가 확인 후 실행했습니다. 기존 파이프라인·파일 보존 테스트는 유지하고 Jinja2 전용 검증을 API 테스트로 전환했습니다.
- `cd frontend && npm test`: **17 passed**, 2개 테스트 파일.
- `npm run typecheck`: 성공. `npm run build`: 성공(index.html·CSS·JS 생성).
- 네트워크 차단 fixture·FakeAgent·fetch/HTTP 경계 모킹만 사용했습니다. 실 LLM·네트워크 호출과 ~/.env 읽기는 하지 않았습니다.
- config.toml·frontend/package.json·package-lock.json의 SHA-256이 작업 시작 시 값과 같았습니다. Git 커밋·푸시는 하지 않았습니다.
- `scripts/list-dependencies.sh`: bash 문법 검사, 임시 uv.lock 유무·Python 항목·scoped/nested npm 출력과 종료 코드 검증 성공.
- 라이선스 표 재생성 결과가 저장된 파일과 동일했습니다. 라이선스 식별자 미확인 행은 없으며 BSD처럼 메타데이터가 세부 변형을 명시하지 않는 경우 그 수준으로 표기했습니다.
- 독립 코드 검토에서 daff 구분자, 비교 재생성 후 화면 캐시, 중첩 HTTP 원인 분류, 키 오류 안내 보존을 수정했습니다. 재검토에서 해당 지적 모두 해결을 확인했습니다. 기준본 변경 폴링과 기준본 변경 중 diff 실패 후 재시도도 회귀 테스트에 포함했습니다.

## 명세 반영과 판단

- 보조 번역기 명세의 자체 HTTP·프롬프트·배치 구현은 design.md의 기존 docutranslate 위임 원칙과 충돌하므로 실제 구현 계약으로 정리했습니다. 라이브러리 소스를 복사하거나 수정하지 않았습니다.
- docutranslate의 verify=False 때문에 환경변수만 지정하는 방식으로는 사내 CA 검증이 되지 않아 요청 경계 서브클래스로 SSLContext를 적용했습니다. 이유·연결 풀 제약은 [ADR-001](../../adr/ADR-001-react-and-intranet-boundaries.md)에 기록했습니다.
- JSON 모드는 기본 false입니다. 사용자 제공 2026-11-17 실측(JSON 배열/json_object 충돌, 해제 후 12/12 성공)을 PROJECT_STATE·명세에 기록했습니다. 지원 여부 자동 탐지나 true 권장은 하지 않습니다.
- 긴 문자 비교의 중간 구간 길이 곱이 1,000,000을 넘으면 메모리 보호를 위해 중간 구간 전체를 강조합니다. 원문은 보존하며 frontend 명세에 한계를 반영했습니다.
- 일반 예외의 원문 메시지는 원문·키가 섞일 수 있어 안전한 요약으로 대체합니다. 기존 changes.json의 위치를 일괄 마이그레이션하지는 않습니다.

## 남은 작업

- **uv.lock 생성 실패:** 기본 uv 캐시 쓰기는 샌드박스에서 거부되었습니다. 기존 메타데이터 캐시를 /tmp로 복사하고 `UV_CACHE_DIR=... uv lock --offline`을 다시 실행했지만 lxml==6.1.3을 다운로드해야 한다는 resolver 오류로 실패했습니다. 잠금 파일을 추정해서 만들지 않았습니다. 사내 미러 반입 후 uv lock 생성·검토·버전 관리 및 frozen 설치 확인이 필요합니다.
- 실제 사내 API/TLS 체인·systemd 실행·브라우저 시각 검토·Office 렌더링은 미실시입니다. 기존 부분 서식·SIGKILL/정전 복구 한계는 PROJECT_STATE에 유지했습니다.
