# 작업 단위 모델 구현 계획

기준: [job-model.md](../job-model.md). Level 3 변경으로, doc/rev 저장·상태·API를 독립 작업으로 대체합니다. 기존 데이터 이전은 하지 않습니다.

- [x] 기존 추출·비교·되쓰기·에이전트를 유지하고 위치/셀 주소 매칭과 언어별 번역 계획 추가
- [x] jobs 저장소, 불변 inputs, 준비 완료 후 원자적 공개, 상태 전이·삭제 구현
- [x] 기존 스트리밍 파서를 4파일로 확장하고 job API·보안 경계·CLI 정리
- [x] 기존 React 컴포넌트로 목록·4칸 업로드·상세 계획/결정/결과 연결
- [x] 매칭·작업 흐름·실패 정리·보안·화면 회귀 테스트를 새 계약으로 전환
- [x] 전체 pytest 및 frontend test/typecheck/build 실행
- [x] AGENTS·운영/설계/상태 문서·ADR·구현 결과 갱신

검증은 임시 Office 파일과 FakeAgent만 사용합니다. config.toml, uv.lock, frontend/package.json, package-lock.json과 패키지 설치 상태를 보존합니다. 기존 엔진·서식/미디어 보존·설정/TLS 테스트를 유지하며, 제거된 doc/rev 동작의 테스트는 새 job 동작으로 대체합니다.
