# ADR-004: 외부 Office 렌더링과 독립 미리보기 상태

## 상태

Accepted — [layout-view.md](../specs/layout-view.md)의 사용자 결정에 따라 구현. 실제 LibreOffice 통합 검증은 현재 실행 환경의 제약으로 미완료이며 [구현 결과](../specs/layout-implementation/result.md)에 기록합니다.

## 배경

[ADR-003](ADR-003-independent-jobs-and-uploaded-memory.md)의 독립 작업·입력 불변·명시적 번역 실행은 유지합니다. 텍스트 변경 목록만으로는 실제 셀·문서 페이지·슬라이드 도형 위치를 찾기 어렵고, 긴 번역은 상태 문자열만으로 진행 정도를 알기 어렵습니다. 새 npm 패키지를 도입하지 않으며 출력 번역 파일은 계속 docutranslate가 생성해야 합니다.

## 검토한 대안

- HTML로 Office 배치를 재구성: Word/PPT의 배치·변경 추적 표현을 별도로 유지해야 하므로 제외.
- 브라우저 Office/PDF 라이브러리: 새 의존성과 복잡한 클라이언트 처리가 필요하므로 제외.
- LibreOffice → PDF → PNG: 서버 글꼴·외부 프로그램 설치가 필요하지만 기존 redline과 Office 문서의 배치를 활용할 수 있음.
- 번역과 같은 긴 잠금으로 렌더링: 업로드·번역 응답과 미리보기 공개가 불필요하게 기다리므로 제외.

## 결정과 근거

1. Word·PPT는 외부 LibreOffice를 셸 없는 인자 목록으로 실행하고, 설치된 pypdfium2 5.15.2로 PNG와 페이지 텍스트를 얻습니다. 독립 프로필·120초 기본 제한·프로세스 그룹 종료·직렬 잠금을 적용합니다. 출력 번역 파일에는 관여하지 않습니다.
2. 업로드 공개 이후 BackgroundTasks에서 실행합니다. `preview`는 작업 `status`와 독립이며 unavailable/failed도 번역을 막지 않습니다. XLSX는 읽기 전용 openpyxl·worksheet XML 메타데이터와 기존 daff 정렬을 이용합니다.
3. 긴 `.pipeline.lock`은 기존대로 유지하고, `.status.lock`을 추가해 상태 필드 병합·미리보기 공개·삭제만 짧게 보호합니다. 렌더러는 최신 상태에 preview만 병합하고 삭제된 작업을 다시 생성하지 않습니다. `.render.lock`은 동일 root 프로세스 사이, 전역 스레드 잠금은 프로세스 내부 PDFium/LibreOffice 실행을 직렬화합니다.
4. `ReuseAgent`는 `progress_batch`(기본 40) 크기로 내부 에이전트를 호출합니다. 묶음 내부 요청·병렬화·재시도는 upstream 그대로입니다. 진행 콜백은 숫자만 전달하고 최근 50개 기록과 ETA를 원자적으로 저장합니다. 중간 저장은 초당 최대 1회, 완료/실패 상태는 마지막 기록과 함께 즉시 저장합니다.

## 결과와 제약

- 원본/수정본·기억·번역 출력 생성 경로와 기존 Host/Origin/업로드/경로 차단 규칙을 유지합니다. 미리보기 이미지도 같은 출처만 허용합니다.
- 글꼴·LibreOffice와 Word의 조판 차이, 순차 텍스트 탐색이 실패한 문단의 기존 위치 표기는 남습니다. Python/npm 라이브러리 소스 수정은 없습니다.
- 영속 큐·자동 재시도·취소를 새로 도입하지 않습니다. 프로세스 강제 종료 시 pending preview 복구는 운영자의 재등록이 필요합니다. 실제 렌더링·브라우저 확인은 일반 로컬 환경에서 수행해야 합니다.
