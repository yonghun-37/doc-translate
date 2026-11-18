# doc-translate

엑셀·워드·파워포인트의 한국어 원본·수정본과 기존 중국어본을 함께 올려 검토하고, 중국어 간체(zh-CN)·번체(zh-TW) 결과를 만드는 도구입니다. **한 번의 업로드가 독립 작업(job)**입니다. 문서명·rev·순서 제약은 없습니다. 원본이 없으면 전체 번역하며, 기존 중국어본이 있으면 원본과 매칭해 수정본의 완전 일치 문장을 재사용합니다. 등록만으로 번역하지 않으며 [번역 실행]을 눌러야 시작합니다.

[작업 모델](docs/specs/job-model.md) · [구현 명세](docs/specs/design.md) · [현재 상태와 한계](docs/PROJECT_STATE.md) · [구조](docs/architecture.md) · [React 웹](docs/specs/frontend-react.md) · [사내 배포](docs/specs/deployment-intranet.md)

## 설치·빌드

Python 3.12와 uv를 사용합니다. 이 작업 환경에는 `.venv/`와 `frontend/node_modules/`가 설치되어 있습니다. 새 환경은 사내 PyPI/npm 미러에서 설치합니다.

```bash
export UV_INDEX_URL=https://<사내-pypi-미러>/simple
uv sync --frozen --python 3.12

cd frontend
npm config set registry https://<사내-npm-미러>/
npm ci
npm run build
cd ..
```

**`uv.lock`과 `frontend/package-lock.json`을 그대로 사용합니다.** 현재 Python 잠금에는 `python-multipart==0.0.34`와 `pypdfium2==5.15.2`가 반영되어 있습니다. 레이아웃 구현은 이미 설치·잠금된 패키지를 사용합니다. 사내 미러 주소·API 키는 저장소에 넣지 않습니다.

이미 설치된 환경에서는 `.venv/bin/python -m app.cli`로 실행할 수 있습니다. CLI 등록이 필요하면 `uv pip install --no-deps -e .`을 사용합니다. `serve`는 FastAPI JSON API와 빌드된 `frontend/dist/`를 제공합니다. 서버에 Node가 없으면 개발 PC의 dist를 앱 소스 옆 `frontend/dist/`로 반입하세요. 빌드가 없으면 웹에 빌드 명령 안내가 나옵니다. 실행 중 CDN이나 의존성 다운로드는 없습니다.

## 설정

- `config.toml.example`: 사내 LLM 주소·모델 자리표시. 주소, 모델, `allowed_hosts`, 키 환경변수를 채웁니다.
- `config.hiveai.toml.example`: 인터넷이 되는 개발 PC용 HiveAI 예시. 별도 설정 파일로 복사하고 `--config`로 선택합니다.
- 기본 설정 경로: `<root>/config.toml`. **기존 로컬 파일은 덮어쓰지 마세요.** 프로그램은 설정을 자동 변환·수정하지 않습니다.

```bash
# 파일이 없는 새 설치에서만
cp config.toml.example config.toml
export DOC_TRANSLATE_API_KEY=...
```

오프라인 기능 시험은 설정을 `fake`로 지정합니다. FakeAgent는 `[zh-CN] 원문`, `[zh-TW] 원문`을 돌려주며 실제 번역이 아닙니다.

```toml
[translator]
engine = "fake"
```

실제 번역 설정과 키 파싱은 [번역기 명세](docs/specs/translator-openai-compatible.md)를 참고하세요.

- `allowed_hosts`: 전송을 허용하는 정확한 호스트 목록. localhost·127.0.0.1·::1은 항상 허용합니다.
- `ca_bundle`: PEM 인증서 경로. 상대 경로는 작업 root 기준이며 `SSL_CERT_FILE`과 검증용 SSLContext에 적용합니다.
- `trust_env_proxy`: 기본 false. true면 환경 프록시·NO_PROXY를 따릅니다.
- 이전 `allow_remote` 항목은 경고를 남깁니다. true이면 선택된 base_url 호스트 하나만 허용 목록에 추가합니다. 로컬 파일은 그대로 둡니다.
- `json_mode=false`가 기본입니다. docutranslate가 요구하는 JSON 배열과 json_object 강제가 충돌해 HiveAI에서 ID 불일치가 발생했습니다. 2026-11-17 사용자 실측은 해제 후 12/12 성공입니다.
- `DOC_TRANSLATE_BASE_URL`, `DOC_TRANSLATE_MODEL`은 파일보다 우선합니다. 키는 지정 환경변수 우선, 없으면 명시한 저장소 밖 키 파일을 읽습니다. 실제 키 파일을 읽는 것은 명시적 번역 실행 때뿐입니다.
- `retry`, `concurrent`, `rpm`, `temperature`, `timeout_sec`, `max_tokens`, `extra_body`는 docutranslate에 전달합니다. `max_retries`는 이전 이름이며 별도 `batch_max_items`·`batch_max_chars`는 사용하지 않습니다.
- `progress_batch`: `[translator.openai_compatible]`에서 기본 40. ReuseAgent가 새 고유 문장을 이 크기로 나누고, 각 묶음의 병렬 요청·재시도는 docutranslate에 맡깁니다. 진행 로그에는 단계·숫자만 저장합니다.
- 용어집: `glossary/glossary.csv`의 `source,zh-CN,zh-TW` 열. 자동 용어집 생성은 끕니다.

## 실행

`--root` 또는 `DOC_TRANSLATE_ROOT`로 데이터 루트를, `--config`로 설정 파일을 지정합니다. 두 옵션은 명령 앞이나 뒤에 둘 수 있고 `--config` 상대 경로는 실행 디렉토리 기준입니다.

```bash
doc-translate serve --host 127.0.0.1 --port 8000 --max-upload-mb 50
# 인증 프록시가 전달하는 호스트가 있다면 --allowed-host HOST 추가 (반복 가능)

# 사용자가 명시적으로 실행할 때만 실제 번역 연결 확인
doc-translate --config /운영경로/config.toml check-translator
```

웹 개발은 API 서버와 `cd frontend && npm run dev`를 함께 실행합니다. Vite가 `/api`를 127.0.0.1:8000으로 프록시합니다. 운영은 `npm run build` 후 FastAPI 하나로 제공합니다.

1. `/` 작업 목록에서 [새 작업]을 누릅니다.
2. `/new`에서 **수정본(한국어, 필수)**, 원본(한국어, 선택), 기존 간체본·번체본(각 선택)을 함께 올립니다. 파일명은 자유이며 네 파일의 확장자가 같아야 합니다. 제목은 수정본 파일명으로 미리 채우고 올린 사람은 선택 입력입니다.
3. `/jobs/:id`의 기본 [원래 모양]에서 Excel 격자, Word 변경 추적 페이지, PPT 원본·수정본과 변경 테두리를 봅니다. [변경 목록]의 위치를 누르면 해당 셀·페이지·슬라이드로 이동합니다. 원본↔수정본 차이와 언어별 기존본 매칭·재사용 예정/새 번역 개수를 확인합니다. 원본이 없으면 `신규 문서 — 전체 번역`입니다. 기존본이 없는 언어도 전체 번역합니다.
4. [번역 실행] 확인 후 번역하며, 진행 중 2초마다 단계·언어별 진행 막대·경과/예상 시간·최근 기록을 확인합니다. 또는 사유를 입력하고 [반려]합니다. 실패하면 오류 요약을 확인하고 [재시도]할 수 있습니다.
5. 두 언어가 모두 성공하면 `<수정본 stem>_zh-CN.ext`, `_zh-TW.ext`를 내려받습니다. 번역 중이 아닌 작업은 확인 대화상자 후 입력·결과까지 전체 삭제할 수 있습니다.

원본과 수정본이 바이트 동일하면 거부합니다. 기본 한도는 **파일당 50MB**(50 × 1024² 바이트)이며 `serve --max-upload-mb`로 바꿉니다. 요청 전체는 최대 네 파일 한도 + 64KiB입니다. 잘못된 형식·손상·검토 준비 실패는 등록하지 않고 임시 파일을 정리합니다.

DOCX·PPTX는 위치 키 그룹, XLSX는 시트·셀 주소와 머리글/바닥글로 기존 중국어본을 매칭합니다. 같은 원문의 후보 번역이 다르면 최빈값(동률 첫 번째)을 사용합니다. **매칭률은 의미 정확도가 아닙니다.** 특히 수동 문단 삽입/삭제로 DOCX 위치 번호가 바뀐 번역본에는 잘못된 대응이 생길 수 있습니다. 매칭 결과와 샘플을 검토하세요.

`openai_compatible`에서 [번역 실행]·[재시도]·check-translator는 실제 API를 사용할 수 있습니다. 서버 시작·업로드·조회는 호출하지 않습니다. 테스트는 FakeAgent/모킹만 사용합니다. process·approve·reject·retry·status CLI와 기존 문서/판 API는 제거했으며 데이터 이전은 제공하지 않습니다.

로그인이 없으므로 127.0.0.1에만 바인딩합니다. 다른 PC 접근은 인증 리버스 프록시와 `--allowed-host`로 구성합니다. Host·동일 출처 검사(POST·DELETE)와 보안 헤더를 적용합니다. 긴 번역은 파일 잠금으로 직렬화하므로 다른 변경 요청이 기다릴 수 있습니다. translating 삭제는 즉시 거부합니다.

systemd 예시는 `deploy/doc-translate.service` 하나입니다. 예시만으로 서비스를 설치·시작하지 않습니다. 서비스 계정에는 jobs·logs 쓰기 권한, `/etc/doc-translate.env`에는 root 소유·권한 600을 적용합니다.

## 저장 파일·의존성

```text
jobs/<YYYYMMDD-HHMMSS-6자리hex>/          # UTC 기반 고유 작업 ID
  status.json                           # 메타데이터·상태·결정·언어별 요약/통계
  inputs/revised.ext                    # 필수, 등록 후 모든 inputs 불변
  inputs/original.ext                   # 선택
  inputs/base_zh-CN.ext, base_zh-TW.ext   # 각각 선택
  review/changes.json                   # 원본↔수정본 변경·위치
  review/redline.docx, redline.pdf       # DOCX 변경 추적·렌더링 PDF
  review/preview/*.png, overlays.json   # Word 페이지/PPT 슬라이드와 도형 좌표
  review/sheets.json | slides.json       # XLSX/PPTX만 (원본 있을 때)
  review/alignment.json                 # 언어별 매칭·미매칭 샘플
  review/memory_zh-CN.json, memory_zh-TW.json
  review/plan.json                       # 언어별 번역 계획
  output/<수정본 stem>_zh-CN.ext, <수정본 stem>_zh-TW.ext
logs/.uploads/                          # 요청·등록 임시 공간
logs/events.jsonl                       # 상태·개수·안전한 오류 요약
logs/library.log                        # 라이브러리 경고/오류 레벨·고정 요약
```

jobs·logs만 데이터 폴더로 사용하며 Git에는 각 `.gitkeep`만 포함합니다. 기존 inbox·versions·review·output 루트 폴더는 제거했습니다. 등록은 임시 job 폴더 전체를 원자적으로 이동하므로 logs와 jobs는 같은 파일시스템에 두세요. 등록 후 inputs·검토 기억은 수정하지 않으며 재시도도 같은 입력을 사용합니다.

문서 원문·번역문·키는 로그에 남기지 않습니다. 검토 산출물·번역 기억에는 업무 텍스트가 있으므로 데이터 폴더 접근을 제한하세요. 다운로드 API는 해당 job의 redline.docx, 준비된 미리보기 PNG·overlays.json과 완료 출력만 제공합니다. 이미지 CSP는 self이며 입력·기억·상태는 공개하지 않습니다.

```bash
scripts/list-dependencies.sh > /tmp/doc-translate-dependencies.tsv
.venv/bin/python scripts/third-party-licenses.py
```

첫 명령은 잠금 파일에서 미러 반입 목록을 출력합니다(uv.lock이 없으면 Python 누락 안내와 종료 코드 1). 두 번째는 설치 메타데이터로 [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md)를 갱신합니다. html2text는 사용되지 않아 uv override로 제외했습니다. docutranslate·certifi·lightningcss는 MPL-2.0, 수정 없이 사용합니다.

## 원래 모양 미리보기

[레이아웃 명세](docs/specs/layout-view.md)와 [구현 결과](docs/specs/layout-implementation/result.md)를 참고하세요. 원본이 있는 작업의 비교를 준비한 뒤 백그라운드에서 미리보기를 만듭니다. 준비 중에는 3초 폴링하며, LibreOffice가 없거나 변환이 실패하면 변경 목록과 번역 실행을 계속 사용할 수 있습니다. Excel 격자는 LibreOffice 없이 표시합니다.

서버에는 `libreoffice-writer-nogui libreoffice-impress-nogui fonts-noto-cjk`(Debian/Ubuntu) 또는 공식 tarball을 설치합니다. LibreOffice는 저장소에 포함하지 않는 외부 프로그램입니다. 문서에 쓰인 회사 글꼴도 라이선스가 허락하면 설치하세요. 글꼴과 Office 버전에 따라 줄바꿈·배치가 달라질 수 있습니다.

```toml
[render]
soffice = ""       # DOC_TRANSLATE_SOFFICE → 이 값 → PATH → /opt/libreoffice*/program/soffice
timeout_sec = 120
max_pages = 300
```

호출마다 독립 프로필을 사용하며 변환은 한 번에 하나, 시간 초과 시 프로세스 그룹을 종료합니다. PDFium은 문서당 최대 300페이지를 긴 변 1600px PNG로 만듭니다. Excel은 최대 2,000행 × 100열이며 변경 주변을 우선 표시합니다. 그보다 많은 변경은 변경 목록에서 위치를 선택해 해당 범위를 불러옵니다.

개발 PC의 사용자 설치를 선택하는 예:

```bash
export DOC_TRANSLATE_SOFFICE="$HOME/.local/opt/lo/opt/libreoffice26.2/program/soffice"
.venv/bin/python -m pytest -q  # 변수 지정 시 실제 LibreOffice 통합 테스트도 실행
```

## 검증과 한계

```bash
.venv/bin/python -m pytest -q
cd frontend && npm test && npm run typecheck && npm run build
```

기본 테스트는 LibreOffice 없이 가짜 PDF·임시 Office 문서·오프라인 에이전트를 사용합니다. `DOC_TRANSLATE_SOFFICE`를 지정하면 실제 변환 통합 테스트 2건을 추가 실행합니다. 실제 사내 API·systemd 실행·Office 화면 검토는 별도 확인 대상입니다. 문단 내 일부 run 서식은 docutranslate 병합에 따라 첫 run 서식을 따를 수 있습니다. 줄바꿈·페이지 배치, SIGKILL/정전의 수동 복구, 위치 표시의 한계는 [현재 상태](docs/PROJECT_STATE.md)를 참고하세요.
