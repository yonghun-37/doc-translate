# 사내 인트라넷 배포 명세

운영 환경은 Linux, 인터넷 없음, Python·npm 패키지는 사내 미러에서 설치하며 번역은 API 키가 필요한 사내 OpenAI 호환 LLM API를 사용합니다. 실제 주소·모델명·미러 주소는 운영 환경에서 제공합니다.

## 1. 설치와 잠금

- 실행 중 외부 CDN·다운로드·텔레메트리를 사용하지 않습니다. Docxodus 실행 파일은 설치 패키지에 포함됩니다.
- Python 3.12, uv와 `frontend/package-lock.json`을 사용합니다. 새 npm 의존성을 추가하지 않습니다.
- 현재 `uv.lock`에는 `python-multipart==0.0.34` 직접 의존성이 반영되어 있습니다. 기존 잠금을 사용해 `uv sync --frozen`으로 설치합니다. 작업 모델 구현에서는 Python/npm 패키지·잠금 파일을 변경하지 않았습니다.
- `html2text`는 docutranslate 선언에는 있지만 import되지 않습니다. `pyproject.toml`의 `[tool.uv] override-dependencies = ["html2text; python_version < '0'"]`로 설치에서 제외합니다. uv를 거치지 않는 pip 설치는 이 정책을 적용하지 않습니다.

```bash
export UV_INDEX_URL=https://<사내-pypi-미러>/simple
uv sync --frozen --python 3.12 # 잠금 파일을 검토·보관한 이후

cd frontend
npm config set registry https://<사내-npm-미러>/
npm ci
npm run build
cd ..

# 기존 config.toml은 보존하고 운영 설정은 별도 경로에 준비할 수 있습니다.
cp config.toml.example /운영경로/config.toml
export DOC_TRANSLATE_API_KEY=...
uv run doc-translate --config /운영경로/config.toml check-translator
uv run doc-translate --config /운영경로/config.toml serve --host 127.0.0.1 --port 8000 --max-upload-mb 50
```

- `scripts/list-dependencies.sh`: uv.lock·package-lock.json에서 이름·버전을 출력합니다. uv.lock이 없으면 npm 목록은 출력하되 Python 목록 누락을 알리고 종료 코드 1을 반환합니다.
- 미러 담당자는 특히 `python-redlines-docxodus`(Linux x64 실행 파일 포함), `docutranslate`, `daff`의 가용성을 확인해야 합니다.
- 서버에 Node가 없으면 개발 PC의 `frontend/dist/`를 앱 소스와 함께 반입합니다. FastAPI의 SPA 경로는 설치된 앱 소스 옆 `frontend/dist/`이며 데이터 `--root`와 독립적입니다. Python wheel만 배포하면 SPA는 별도 반입이 필요합니다.
- `scripts/third-party-licenses.py`는 설치 환경에서 이름·버전·라이선스 표를 다시 생성합니다. 현재 목록은 [THIRD_PARTY_LICENSES.md](../../THIRD_PARTY_LICENSES.md)이며 MPL-2.0 항목은 수정 없이 사용합니다.

## 2. 서비스

- `deploy/doc-translate.service`: 업로드·검토·명시적 번역 실행을 제공하는 웹 서버 하나만 운영합니다.
- doc/rev·inbox 감시·관리자 process/approve/reject/retry/status CLI는 제거했습니다. serve·check-translator만 사용합니다. 이전 서비스가 있다면 운영자가 중지·제거한 뒤 웹 서비스 하나로 전환합니다. 기존 데이터 이전은 제공하지 않습니다.
- 예시의 `/opt/doc-translate`, 서비스 계정 `doc-translate`, 설정 경로를 실제 설치 환경에 맞게 변경합니다.
- `/etc/doc-translate.env`에 API 키 등 환경변수를 두고 소유자 root, 권한 600으로 관리합니다. systemd가 읽고 서비스에 전달합니다. 실제 키 파일은 저장소에 넣지 않습니다.
- 서비스 계정은 `<root>/jobs/`와 `<root>/logs/`에 쓸 수 있어야 합니다. logs/.uploads에서 준비한 작업을 jobs로 원자적 이동하므로 두 폴더는 같은 파일시스템에 둡니다. 입력은 `jobs/<id>/inputs/`에 보관하며 등록 후 수정하지 않습니다. 작업 삭제는 입력·검토·출력 전체를 제거합니다.
- 예시는 서비스를 설치·활성화하지 않습니다. 프로세스 실행은 `.venv/bin/doc-translate`를 직접 사용하므로 시작 시 의존성 다운로드가 없습니다.
- 웹은 127.0.0.1 전용이며 로그인 기능이 없습니다. 타 PC 접근이 필요하면 사내 인증이 있는 리버스 프록시 뒤에 배치합니다. 프록시 Host/Origin은 백엔드의 로컬 호스트·동일 출처 검사에 맞춰 설정하고 외부 접근 인증을 별도로 적용해야 합니다.
- 프록시가 전달하는 Host 이름은 `serve --allowed-host <호스트>`(여러 번 지정 가능)로 허용합니다. 바인딩은 계속 127.0.0.1이며, 다른 사이트 Origin의 POST·DELETE는 그대로 403입니다. 개발 PC 예: `tailscale serve --bg --https=8765 http://127.0.0.1:8765` + `--allowed-host <기기>.<tailnet>.ts.net` (tailnet 전용, Funnel 사용 금지).

### 업로드 운영 설정

- `serve --max-upload-mb 50`은 파일 한도 50 × 1024² 바이트를 뜻하며 양의 정수로 변경할 수 있습니다. 별도의 config.toml 수정은 필요 없습니다.
- 앱은 multipart를 스트리밍으로 받아 파일 한도 초과 즉시 413을 반환합니다. 최대 네 파일의 각 한도를 검사하며 요청 전체는 `4 × 파일 한도 + 64KiB`로 제한하고, 검증 실패·연결 중단 때 임시 파일을 정리합니다. 프록시 본문 제한은 multipart 여유분까지 허용하고 필요하면 요청 버퍼링을 끄세요. 프록시의 선행 제한은 앱보다 먼저 응답할 수 있습니다.
- `/new`에서 원본·수정본·기존 간체본·기존 번체본을 함께 올립니다. 수정본 필수, 나머지 선택이며 모든 확장자가 같아야 합니다. 한 번의 업로드가 독립 작업이고 파일명·문서별 순서 제약은 없습니다. diff·매칭·번역 계획 준비 후 pending으로 공개하고 [번역 실행] 확인 전에는 LLM을 호출하지 않습니다. 원본이 없으면 전체 번역입니다.
- 등록·번역은 동일 잠금으로 직렬화하므로 큰 문서 비교나 번역 중 업로드 등록이 기다릴 수 있습니다. 디스크 공간은 동시 수신 네 파일·등록 복사·비교 산출물·두 언어 임시 출력까지 고려합니다. translating 상태에서 삭제 요청은 409입니다.
- 강제 종료·정전으로 남은 임시 파일이나 작업의 수동 복구는 [현재 상태](../PROJECT_STATE.md)의 한계를 따릅니다.

## 3. LLM 연결과 검증

설정은 [translator-openai-compatible.md](translator-openai-compatible.md) 2.0절을 따릅니다. `allowed_hosts`에는 사내 LLM만 넣고 필요한 경우 `ca_bundle`, `trust_env_proxy`를 지정합니다.

`check-translator`는 명시적으로 실행할 때만 현재 설정으로 두 언어 연결·번역을 확인하며 언어별 소요 시간·추론 토큰 수(미제공이면 안내)를 출력합니다. `json_mode=false`가 기본입니다. json_object 지원 여부만으로 true를 권장하지 않습니다. docutranslate의 JSON 배열과 충돌해 HiveAI에서 ID 불일치가 발생했으며, 2026-11-17 사용자 실측은 비활성화 후 12/12 성공입니다. JSON 모드 자동 탐지·설정 변경은 하지 않습니다.

오프라인 검증 명령:

```bash
.venv/bin/python -m pytest -q
cd frontend && npm test && npm run typecheck && npm run build
```

실제 사내 API·systemd 시작·Office 렌더링 확인은 배포 환경에서 수행합니다.
