# OpenAI 호환 번역 엔진 명세

HTTP 요청·배치·재시도·응답 파싱은 [design.md](design.md) 6절에 따라 **docutranslate 1.7.11 `SegmentsTranslateAgent`에 위임**합니다. 앱은 설정 검증, 키 조회, TLS/프록시 정책, 번역 재사용과 실패 판정을 담당합니다. 이전 보조 명세의 자체 HTTP 클라이언트·별도 배치 알고리즘은 구현하지 않습니다.

## 1. 원칙

- `translator.engine`: `fake`(오프라인 기능 시험) 또는 `openai_compatible`(실제 번역). 설정 파일이 없을 때도 사내 설정 기본값을 사용하지만, 빈 `allowed_hosts` 때문에 외부 호출은 차단됩니다.
- 호환 서버의 `{base_url}/chat/completions`에 docutranslate가 요청합니다. 공급자별 SDK나 별도 번역 엔진을 추가하지 않습니다.
- 키는 환경변수 또는 명시적으로 지정한 저장소 밖 키 파일에서만 읽습니다. 설정 파일에 키 값을 저장하지 않습니다.
- 실제 API 호출은 사용자가 번역 처리·승인·재시도·연결 확인을 실행할 때만 발생합니다. 웹 서버 시작과 조회는 번역을 호출하지 않습니다.
- 개발 테스트는 FakeAgent 또는 HTTP 경계 모킹을 사용합니다. 네트워크와 실제 키 파일 접근은 하지 않습니다.

## 2. 설정

```toml
[translator]
engine = "openai_compatible"

[translator.openai_compatible]
base_url = "http://localhost:11434/v1"
model = "local-model"
api_key_env = "DOC_TRANSLATE_API_KEY" # 인증 없는 로컬 서버는 빈 문자열
api_key_file = ""                   # 환경변수 없을 때 사용할 저장소 밖 경로
allowed_hosts = []                  # localhost, 127.0.0.1, ::1은 항상 허용
ca_bundle = ""                      # PEM 인증서 경로; 상대 경로는 작업 root 기준
trust_env_proxy = false             # true면 HTTP_PROXY/HTTPS_PROXY/NO_PROXY 적용
temperature = 0
timeout_sec = 180
retry = 3
concurrent = 4
json_mode = false                   # response_format=json_object 강제 여부
max_tokens = 4096                   # 0이면 별도로 전달하지 않음
extra_body = {}
# rpm = 10                         # 선택: 분당 요청 제한
```

- `--config /경로/설정.toml`로 설정 파일을 선택합니다. 기본은 `<root>/config.toml`; 명시한 파일이 없으면 오류입니다. `--config` 상대 경로는 CLI 실행 디렉토리 기준입니다.
- `DOC_TRANSLATE_BASE_URL`, `DOC_TRANSLATE_MODEL`은 파일보다 우선합니다.
- 키 우선순위: `api_key_env` → `api_key_file`. 첫 유효 줄의 `이름표:키`, `KEY=키`, `export KEY="키"`, 키만 있는 형식을 지원합니다. 저장소 안 키 파일은 거부합니다.
- `allowed_hosts`는 정확한 호스트 이름 목록입니다. 스킴·포트·경로·와일드카드를 넣지 않습니다. 대소문자는 구분하지 않습니다.
- `ca_bundle` 지정 시 파일 존재를 확인하고 `SSL_CERT_FILE`을 설정합니다. 라이브러리의 기본 클라이언트가 `verify=False`이므로 앱의 `SecureSegmentsAgent`가 요청 경계에서 검증 가능한 SSLContext를 가진 httpx 클라이언트를 사용합니다. CA 검증과 프록시 사용 여부는 독립적입니다. 리디렉션은 따라가지 않습니다.
- `trust_env_proxy=false`는 환경 프록시를 사용하지 않습니다. true면 httpx의 환경 프록시·NO_PROXY 처리를 사용합니다. upstream의 별도 프록시 마운트는 비활성화합니다.
- `max_retries`는 `retry`의 이전 이름으로 읽습니다. 이전 `batch_max_items`·`batch_max_chars`는 읽되 사용하지 않습니다. 별도 `extra_headers` 설정은 지원하지 않습니다.

### 2.0 운영: 사내 인트라넷 LLM

`config.toml.example`은 사내 주소·모델 자리표시입니다. 이미 사용하는 로컬 `config.toml`은 자동 변환하거나 덮어쓰지 않습니다.

```toml
[translator]
engine = "openai_compatible"
[translator.openai_compatible]
base_url = "https://llm.example.internal/v1"
model = "TODO-model-name"
api_key_env = "DOC_TRANSLATE_API_KEY"
api_key_file = ""
allowed_hosts = ["llm.example.internal"]
ca_bundle = ""
trust_env_proxy = false
temperature = 0
json_mode = false
max_tokens = 4096
timeout_sec = 180
```

사내 서버의 주소·모델·인증서·키를 운영 환경에 맞게 설정한 뒤 `check-translator`를 명시적으로 실행합니다. `thinking="disable"` 등 공급자별 매핑은 docutranslate에 위임하며 서버별 호환성은 실제 연결 시험에서 확인해야 합니다.

### 2.1 개발용: HiveAI DeepSeek

인터넷이 되는 개발 PC에서 사용자가 선택한 경우에만 씁니다. `config.hiveai.toml.example`을 별도 파일로 복사하고 `--config`로 지정합니다.

```toml
[translator]
engine = "openai_compatible"
[translator.openai_compatible]
base_url = "https://api-sf1-cdn.deploy.com/api/v1"
model = "deepseek-ai/deepseek-v4.1-flash-1017"
api_key_env = "DEPLOY_API_KEY"
api_key_file = "~/.env"
allowed_hosts = ["api-sf1-cdn.deploy.com"]
ca_bundle = ""
trust_env_proxy = false
temperature = 0
json_mode = false
max_tokens = 16384
timeout_sec = 180
```

**2026-11-17 사용자 실측:** docutranslate는 `[{"id":"0","t":"번역"}, ...]` 형태의 JSON **배열**을 요구합니다. `response_format={"type":"json_object"}`가 이를 객체로 강제하여 HiveAI DeepSeek에서 간헐적인 ID 불일치가 발생했습니다. `json_mode=false`로 끈 뒤 **12/12 성공**했습니다. 따라서 API가 json_object 옵션을 수락한다는 사실만으로 모드를 켜지 않습니다. 이 결과는 사용자가 전달한 실측이며 2차 개발 과정에서 실제 API를 재호출하지 않았습니다.

앞선 단건 시험은 세그먼트 2개 번체 번역에 약 12초, `finish_reason=stop`, `reasoning_tokens=147`이었습니다(사용자 제공). 분리된 추론 내용은 번역 결과나 로그에 넣지 않습니다.

## 3. 원격 전송 가드와 하위 호환

- localhost·127.0.0.1·::1 또는 `allowed_hosts`에 있는 호스트만 허용합니다. 키 파일 조회와 에이전트 생성 전에 검증합니다.
- **이전 `allow_remote` 호환:** 항목이 존재하면 경고 로그를 남깁니다. 값이 true이면 로딩 시 선택된 `base_url`의 호스트 하나만 `allowed_hosts`에 추가합니다. false이면 추가하지 않습니다. 호환 처리는 설정 파일을 쓰거나 삭제하지 않습니다. 모든 원격 호스트를 허용하는 와일드카드 동작은 남기지 않습니다.
- 이전 `allow_remote=true`와 `DOC_TRANSLATE_BASE_URL`을 함께 사용하면 환경변수로 최종 선택한 호스트가 추가됩니다. 이 호환 예외를 없애려면 사용자가 명시적인 `allowed_hosts`로 옮겨야 합니다.
- 운영 허용 목록에는 사내 LLM 호스트만 넣습니다. 설정 허용 목록은 의도한 전송 대상을 확인하는 장치이며 네트워크 방화벽을 대체하지 않습니다.

## 4. 번역 계약과 실패

- `base_url→base_url`, `model→model_id`, `json_mode→force_json`, `timeout_sec→timeout`, 키→`api_key`로 매핑합니다. `max_tokens`는 `extra_body` JSON에 병합합니다.
- 대상 언어는 `简体中文`, `繁體中文（台灣）`이며 번체에는 대만 용어 지시를 추가합니다. 용어집은 언어별 `glossary_dict`로 전달하고 자동 용어집 생성은 끕니다.
- 프롬프트·JSON 배열 파싱·코드 펜스 처리·분할·재시도는 설치된 docutranslate의 동작을 따릅니다. 앱이 별도의 공급자 프로토콜이나 재시도 횟수를 보장하지 않습니다.
- `ReuseAgent`는 완전 일치 원문 재사용, 신규 텍스트 중복 제거, 숫자/단위 제외, 결과 길이·빈 결과·`unresolved_errors`를 검증합니다. upstream의 원문 fallback도 실패로 처리합니다.
- 두 언어 모두 성공해야 파일과 번역 메모리를 공개합니다. 실패 시 `status.json`과 `events.jsonl`에 예외 종류·안전한 요약을 남깁니다. HTTP 상태·인증·시간 초과·연결 실패는 원인별로 구분합니다. 임의 예외 원문은 문서·키가 섞일 수 있어 저장하지 않습니다.
- `logs/library.log`에는 경고/오류의 시각·레벨·고정 요약만 남기며 메시지·인자·traceback·응답 본문을 기록하지 않습니다.

## 5. CLI와 검증

```bash
doc-translate --config config.toml check-translator
doc-translate retry '설계서' 2
```

`check-translator`는 현재 설정으로 한 문장을 두 언어에 각각 요청합니다. JSON 모드 자동 탐지나 자동 설정 변경은 하지 않습니다. 현재 json_mode 값과 언어별 소요 시간·upstream에서 제공하는 추론 토큰 수를 출력합니다. 추론 본문은 출력하지 않습니다. 실제 API는 해당 명령을 사용자가 실행할 때만 요청합니다.

오프라인 테스트는 허용 호스트·호환 경고·키 우선순위·CA/프록시 전달·TLS 요청 경계·설정 경로·실패 복구·민감정보 제외를 검증합니다. 실제 사내 서버와 HiveAI의 품질·인증서 체인은 별도 운영 확인 대상입니다.
