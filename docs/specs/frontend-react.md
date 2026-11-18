# 작업 웹: FastAPI JSON API + React SPA

변경 위치·원래 모양·번역 진행은 [layout-view.md](layout-view.md)를 따릅니다. 작업·매칭·입력 정책은 [job-model.md](job-model.md)가 우선합니다. doc/rev 화면과 web-upload.md의 문서별 업로드는 대체되었습니다.

## 구조

`frontend/src/App.tsx`의 React Router, `api.ts`의 fetch/응답 타입, React Query 조회·폴링을 유지합니다. 목록·업로드·상세는 기존 `ReviewList`, `Upload`, `ReviewDetail`을 확장합니다. `ChangeTable`, `InlineDiff`, `SheetDiff`, `SlideDiff`, `DecisionPanel`, `OutputFiles`, `StatusBadge`를 재사용하고 `TranslationPlan`을 추가합니다.

설치된 React·TypeScript·Vite·Router·React Query·Vitest·Testing Library를 그대로 사용합니다. 새 패키지·CDN·UI 프레임워크를 도입하지 않습니다. CSS는 `styles.css`입니다.

운영은 `npm run build`로 만든 `frontend/dist/`를 FastAPI가 assets 및 SPA 폴백으로 제공합니다. 빌드가 없으면 빌드 안내를 반환합니다. 개발은 serve와 Vite dev 프록시를 사용합니다. 알려지지 않은 `/api/*`는 404이며 SPA로 처리하지 않습니다.

## 화면

### `/` 작업 목록

- 최신순 제목·형식·상태·추가/삭제/수정 건수·간체/번체 매칭·올린 사람·생성 시각.
- 매칭 예: `간체 20/22 · 번체 없음`. 상태 필터·제목 검색, 행/제목 링크로 상세 이동.
- 상단 [새 작업] → `/new`. 10초 자동 갱신.

### `/new` 업로드

- 원본(한국어, 선택), 수정본(한국어, 필수), 기존 간체본(선택), 기존 번체본(선택)의 네 파일 칸.
- docx·xlsx·pptx, 모든 확장자 일치. 각 칸에 선택 파일명, 형식 오류 즉시 표시. 수정본이 없거나 형식 오류가 있으면 제출 불가.
- 제목은 수정본 파일명으로 미리 채움. 수정하거나 비울 수 있으며 서버에서 빈 제목을 기본값으로 처리.
- 올린 사람과 검토자 이름은 `doc-translate.reviewer` localStorage를 공유.
- 원본을 비우면 전체 번역 안내. 중국어본을 함께 올려도 원본이 없으면 재사용하지 않음.
- FormData로 전송하며 Content-Type boundary는 브라우저가 설정. 전송 중 전체 폼·중복 제출 잠금, 업로드/검토 준비 중 표시.
- 실패하면 오류 배너에 포커스를 이동하고 파일·필드 유지. 성공하면 목록 캐시 갱신 후 `/jobs/:id`로 이동.

### `/jobs/:id` 상세

- 제목·상태·생성/결정 시각·올린 사람·결정자·입력 네 파일 이름·반려 사유.
- 원본 없음: `신규 문서 — 전체 번역`, 형식별 비교 요청 생략.
- 원본 있음: [원래 모양] 기본 탭과 [변경 목록]. SheetView(격자·시트 탭·삭제 행 펼치기·이전/다음 변경), PageView(페이지·썸네일·변경 수·지연 로딩), SlideCompare(원본/수정본·도형 테두리·노트·변경 필터)를 사용합니다. 목록의 위치 버튼/행 클릭은 원래 모양 위치로 이동합니다. 기존 ChangeTable·InlineDiff·SheetDiff·SlideDiff는 변경 목록에서 유지합니다.
- preview pending은 3초 폴링, unavailable/failed는 안내와 변경 목록으로 전환합니다. 변경이 없는 신규 문서와 이전 작업의 표시 규칙은 유지합니다.
- 번역 계획: 언어별 재사용 예정/새 번역 개수, 원본 매칭 수, 미매칭 샘플 최대 20개 펼치기, 50% 미만 경고. 원본 없는 기존본은 재사용 불가 안내.
- pending: [번역 실행] 확인 대화상자, 선택 검토자 이름, 사유 필수 [반려].
- translating: 2초 폴링·TranslationProgress 단계/언어별 막대·경과/예상 시간·최근 기록, 삭제 비활성화. 완료 시 두 언어 다운로드·언어별 통계 표시.
- failed: 안전한 오류 요약·[재시도].
- translating 외 [작업 삭제] 확인 대화상자, 성공 시 목록으로 이동. 상태 충돌 409는 안내 후 다시 조회.

한국어 UI, 키보드 포커스/명시적 레이블/상태 알림을 유지합니다. 좁은 화면에서 파일 칸·언어 계획은 한 열, 비교 표는 가로 스크롤을 사용합니다. HTML 삽입 없이 텍스트를 렌더링합니다. InlineDiff는 비교 구간 길이 곱이 1,000,000을 넘으면 공통 앞뒤 외 중간 전체를 삭제/추가로 강조합니다. daff 가변 구분자(`->`, `-->` 등)는 행 marker 전체를 사용합니다.

## API 계약

| 메서드·경로 | 응답 |
| --- | --- |
| GET `/api/jobs` | `JobSummary[]`, 최신순 |
| POST `/api/jobs` | multipart: original?, revised, base_zh_cn?, base_zh_tw?, title?, by?; 201 `JobDetail` |
| GET `/api/jobs/{id}` | `JobDetail` |
| GET `/api/jobs/{id}/sheets` / `slides` | 기존 `SheetDiff[]` / `SlideDiff[]`; 다른 형식은 404, 원본 없으면 빈 목록 |
| GET `/api/jobs/{id}/grid` | 시트별 격자·변경·삭제 행·표시 제한; 선택 query sheet/row/col로 이동 범위 지정 |
| GET `/api/jobs/{id}/files/preview/{name}` | ready 상태의 PNG 또는 overlays.json, 같은 출처·경로/심볼릭 링크 검사 |
| POST `/api/jobs/{id}/translate` | `{by?}`, pending에서 202, translating 응답 후 BackgroundTasks |
| POST `/api/jobs/{id}/reject` | `{reason, by?}`, pending에서 200; 빈 사유 400 |
| POST `/api/jobs/{id}/retry` | failed에서 202, translating 응답 |
| DELETE `/api/jobs/{id}` | 204; translating이면 409 |
| GET `/api/jobs/{id}/files/{name}` | redline·공개된 출력 파일. inputs·메모리·status 다운로드 불가 |

타입 정의는 `frontend/src/api.ts`, 서버 대응 모델은 `app/web/models.py`입니다.

- Status: pending / translating / translated / failed / rejected.
- JobSummary: id, title, ext, status, counts, created_at, uploaded_by, alignment(언어별 total/matched).
- JobDetail: 요약 + files(표시 이름), decided_at/by, reason, error, changes, alignment(언어별 lang/total/matched/unmatched_samples), plan(언어별 segments/reused/translated), artifacts(redline URL), outputs(lang/url 목록), stats(언어별 실제 통계), preview(별도 상태·메시지·페이지 메타데이터), progress(단계·언어별 수치·시각·ETA·기록). Change에는 page/slide/sheet/cell/source 선택 필드를 추가합니다.
- 기존 중국어본이 없는 언어는 alignment 항목 없음. 원본 없이 기존본만 있으면 0/0. plan은 항상 두 언어, stats는 완료 전 빈 객체.
- 상태 충돌은 409, 잘못된 업로드/손상은 400, 크기 초과는 413, 다른 출처의 변경 요청은 403.
- `/api/documents`, `/api/uploads`, `/api/reviews`, 전역 파일 API는 제거.

## 검증

fetch 모킹으로 최신순 목록·검색/필터·자동 갱신, 네 파일 폼·필수/형식 검증·제목·이름 저장·진행·오류·이동, 비교 컴포넌트·문자 강조·HTML 이스케이프, 번역 계획·경고·미매칭 샘플, 실행 확인·반려·충돌·재시도·2초 폴링·언어별 결과·삭제를 검증합니다. 서버는 TestClient와 FakeAgent로 실제 API 경계를 검사합니다.

`npm test`, `npm run typecheck`, `npm run build`가 모두 성공해야 합니다. jsdom에서 required 파일 입력이 user-event FileList를 읽지 못하는 제약은 테스트의 native 검증만 우회하고 앱·서버 검증은 유지합니다.

서버 `[render]`는 외부 변환 경로·120초 제한·문서당 300페이지를 제어합니다. `[translator.openai_compatible] progress_batch=40`은 진행 갱신 단위이며 UI 설정 칸은 추가하지 않습니다. 이미지 CSP는 `img-src 'self'`를 유지하고 SVG 테두리는 React 속성으로 렌더링합니다. 셀 툴팁 정보는 aria-label에도 제공하며 변경 셀은 키보드로 포커스할 수 있습니다. 두 탭 그룹은 화살표/Home/End를 지원합니다.
