# 2차 구현 계획

> 이전 구현의 기록입니다. 현재 입력은 [웹 업로드](../web-upload.md)로 전환했으며 감시·신규 자동 번역은 제거했습니다. 최신 상태는 [업로드 구현 결과](../upload-implementation/result.md)를 참고하세요.

기준: [React 웹](../frontend-react.md), [사내 배포](../deployment-intranet.md), [번역 설정](../translator-openai-compatible.md), [기존 설계](../design.md).

사용자가 지정한 React·JSON API 전환과 인트라넷 준비를 구현한다. 기존 파이프라인·번역 재사용·원본 불변 계약은 보존한다. 구조 변경(Level 3)이므로 결과, 현재 구조, ADR을 함께 갱신한다.

## 제약과 판단

- 실제 LLM/네트워크 호출, `~/.env` 읽기, 커밋 금지. `config.toml`은 변경하지 않는다.
- npm 패키지·잠금 파일은 그대로 사용. Python 잠금은 `uv lock --offline`으로 시도한다.
- 모든 기존 파일이 미추적 상태이므로 현재 작업 공간에서 수정한다. 초기 소스 사본과 로컬 설정 해시를 `/tmp`에 보관해 변경 범위를 검토한다.
- 명세의 직접 HTTP 구현 예시는 기존 design.md의 docutranslate 위임 원칙에 맞춰 정정한다.
- JSON 배열 응답과 json_object 충돌 때문에 `json_mode=false`를 기본으로 유지한다.
- 에러 메시지는 안전하게 분류·축약하며, 알 수 없는 라이브러리 메시지 원문은 저장하지 않는다.

## 작업

- [x] React SPA: `frontend/` 설정·컴포넌트·fetch 타입·테스트. 명세의 API 계약을 사용한다. 기존 패키지와 CSS 하나만 사용한다.
- [x] JSON API: `app/web/` Pydantic 응답, 목록·상세·결정·재시도·파일, daff JSON, SPA 폴백. API 회귀 테스트를 먼저 추가한다.
- [x] 설정·CLI: `allowed_hosts`, 레거시 경고, CA·프록시 실제 라이브러리 전달, `--config`, `retry`. 오프라인 매핑·가드 테스트로 검증한다.
- [x] 진단·위치: 안전한 예외 요약과 library.log, 추출 요소의 docx/pptx 위치. 실패·민감정보·위치 회귀 테스트를 추가한다.
- [x] 배포: 예시 설정 분리, html2text 제외, 오프라인 잠금 시도(캐시 부족 실패), 의존성·라이선스 스크립트와 표, systemd 예시.
- [x] 통합 검증: pytest, npm test, typecheck, build. 로컬 설정/원본/패키지 잠금 보존 확인. 결과·현재 상태·명세·구조·ADR 갱신.

## 검토 초점

- 경로 탈출·심볼릭 링크·API 경로에 SPA HTML이 반환되는 경우.
- 승인 기준본 변경(409)과 백그라운드 번역 중 폴링, 중복 승인·재시도.
- URL 환경변수와 레거시 원격 허용의 상호작용, CA와 프록시의 실제 전달.
- 예외에 원문·API 키·응답 본문이 포함되는 경우와 로그의 정보 손실 균형.
- 중복 텍스트·표 셀·노트·마스터 위치와 이전 산출물 호환.

## 남은 배포 준비

- [ ] 사내 미러에서 uv.lock 생성·검토·버전 관리 후 frozen 설치 확인. 오프라인 실패 근거는 result.md와 PROJECT_STATE.md에 기록했다.
