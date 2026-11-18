"""Configuration only; HTTP, chunking, and retries belong to docutranslate."""
import csv
import json
import logging
import math
import os
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

LANGUAGES = {'zh-CN': '简体中文', 'zh-TW': '繁體中文（台灣）'}
QUIET_LOGGER = logging.Logger('doc-translate.library')
QUIET_LOGGER.addHandler(logging.NullHandler())
QUIET_LOGGER.propagate = False


class ConfigError(ValueError):
    pass


@dataclass
class RenderConfig:
    soffice: str = ''
    timeout_sec: int = 120
    max_pages: int = 300

    def __post_init__(self):
        if (not isinstance(self.soffice, str) or type(self.timeout_sec) is not int
                or self.timeout_sec <= 0 or type(self.max_pages) is not int or self.max_pages <= 0):
            raise ConfigError('render 경로는 문자열, 시간 제한·최대 페이지는 양의 정수여야 합니다.')


def parse_key(content: str) -> str:
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if line.startswith('export '):
            line = line[7:].strip()
        label = re.match(r'^[^:=\s]+:\s*(.*)$', line)
        assignment = re.match(r'^[A-Za-z_]\w*\s*=(?!=)\s*(.*)$', line)
        if label:
            line = label[1]
        elif assignment:
            line = assignment[1]
        key = line.strip().strip('\"\'').strip()
        if key:
            return key
    raise ConfigError('키 파일에 유효한 키가 없습니다.')


@dataclass
class Config:
    root: Path
    engine: str = 'openai_compatible'
    base_url: str = 'https://llm.example.internal/v1'
    model: str = 'TODO-model-name'
    api_key_env: str = 'DOC_TRANSLATE_API_KEY'
    api_key_file: str = ''
    allowed_hosts: list[str] = field(default_factory=list)
    ca_bundle: str = ''
    trust_env_proxy: bool = False
    # Accepted only for old local files and callers; never a wildcard policy.
    allow_remote: bool | None = field(default=None, repr=False)
    temperature: float = 0
    max_tokens: int = 16384
    timeout_sec: int = 180
    json_mode: bool = False
    retry: int = 3
    concurrent: int = 4
    rpm: int | None = None
    extra_body: dict = field(default_factory=dict)
    progress_batch: int = 40
    render: RenderConfig = field(default_factory=RenderConfig)

    def __post_init__(self):
        if type(self.progress_batch) is not int or self.progress_batch < 1:
            raise ConfigError('progress_batch는 양의 정수여야 합니다.')
        if self.allow_remote is not None:
            logging.getLogger(__name__).warning(
                'allow_remote는 폐기 예정입니다. 현재 base_url 호스트만 allowed_hosts에 추가합니다(값이 true인 경우).')
            if self.allow_remote is True and isinstance(self.allowed_hosts, list):
                try:
                    host = urlsplit(self.base_url).hostname
                except (TypeError, ValueError):
                    host = None
                if host and host not in self.allowed_hosts:
                    self.allowed_hosts = [*self.allowed_hosts, host]

    @classmethod
    def load(cls, root: Path, config_path: Path | str | None = None):
        root = Path(root).resolve()
        path = Path(config_path).expanduser().resolve() if config_path is not None else root / 'config.toml'
        if config_path is not None and not path.is_file():
            raise ConfigError('설정 파일을 찾을 수 없습니다.')
        try:
            data = tomllib.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
            translator = data.get('translator', {})
            options = dict(translator.get('openai_compatible', {}))
            if 'max_retries' in options:
                options.setdefault('retry', options.pop('max_retries'))
            # Legacy batching settings are intentionally not an app implementation.
            for name in ('batch_max_items', 'batch_max_chars'):
                options.pop(name, None)
            for env, key in [('DOC_TRANSLATE_BASE_URL', 'base_url'), ('DOC_TRANSLATE_MODEL', 'model')]:
                if env in os.environ:
                    options[key] = os.environ[env]
            return cls(root=root, engine=translator.get('engine', 'openai_compatible'),
                       render=RenderConfig(**data.get('render', {})), **options)
        except (TypeError, AttributeError, OSError, tomllib.TOMLDecodeError):
            raise ConfigError('config.toml의 설정 형식 또는 항목을 확인하세요.') from None

    def validate(self):
        if self.engine not in {'fake', 'openai_compatible'}:
            raise ConfigError('번역 엔진은 fake 또는 openai_compatible이어야 합니다.')
        if self.engine == 'fake':
            return
        if any(type(v) is not bool for v in (self.json_mode, self.trust_env_proxy)) or (self.allow_remote is not None and type(self.allow_remote) is not bool):
            raise ConfigError('json_mode, trust_env_proxy, 이전 allow_remote는 true 또는 false여야 합니다.')
        if not isinstance(self.allowed_hosts, list) or any(not isinstance(h, str) or not h or not re.fullmatch(r'[A-Za-z0-9.:-]+', h) for h in self.allowed_hosts):
            raise ConfigError('allowed_hosts는 와일드카드·URL 없는 호스트 이름 목록이어야 합니다.')
        if not isinstance(self.ca_bundle, str):
            raise ConfigError('ca_bundle 인증서 경로는 문자열이어야 합니다.')
        if self.ca_bundle and not self.ca_path().is_file():
            raise ConfigError('ca_bundle 인증서 파일을 찾을 수 없습니다.')
        if any(type(v) is not int for v in (self.timeout_sec, self.concurrent, self.retry, self.max_tokens)) or (self.rpm is not None and type(self.rpm) is not int):
            raise ConfigError('시간 제한·동시 요청·재시도·토큰·RPM은 정수여야 합니다.')
        if type(self.temperature) not in {int, float} or not math.isfinite(self.temperature):
            raise ConfigError('temperature는 유한한 숫자여야 합니다.')
        if not isinstance(self.api_key_env, str) or not isinstance(self.api_key_file, str):
            raise ConfigError('키 환경변수 이름과 파일 경로는 문자열이어야 합니다.')
        if not isinstance(self.model, str) or not self.model.strip():
            raise ConfigError('번역 모델을 지정하세요.')
        try:
            url = urlsplit(self.base_url)
            port = url.port
            valid = url.scheme in {'http', 'https'} and url.hostname and not (url.username or url.password or url.query or url.fragment)
        except (ValueError, TypeError):
            valid = False
        if not valid:
            raise ConfigError('base_url은 인증정보·쿼리 없는 HTTP(S) 주소여야 합니다.')
        if url.hostname not in {'localhost', '127.0.0.1', '::1'} and url.hostname.lower() not in {h.lower() for h in self.allowed_hosts}:
            raise ConfigError('원격 전송이 차단되었습니다. allowed_hosts 설정을 확인하세요.')
        if not isinstance(self.extra_body, dict):
            raise ConfigError('extra_body는 TOML 테이블이어야 합니다.')
        if self.timeout_sec <= 0 or self.concurrent < 1 or self.retry < 0 or self.max_tokens < 0 or (self.rpm is not None and self.rpm < 1):
            raise ConfigError('시간 제한·동시 요청·재시도·토큰·RPM 설정을 확인하세요.')

    def ca_path(self) -> Path:
        path = Path(self.ca_bundle).expanduser()
        return (path if path.is_absolute() else self.root / path).resolve()

    def resolve_key(self) -> str | None:
        if self.api_key_env and (key := os.environ.get(self.api_key_env, '').strip()):
            return key
        if self.api_key_file:
            path = Path(self.api_key_file).expanduser()
            if not path.is_absolute():
                path = self.root / path
            path = path.resolve()
            if path.is_relative_to(self.root.resolve()):
                raise ConfigError('키 파일은 저장소 밖에 있어야 합니다.')
            try:
                return parse_key(path.read_text(encoding='utf-8'))
            except OSError:
                raise ConfigError('키 파일을 읽을 수 없습니다. 환경변수 또는 키 파일을 확인하세요.') from None
        if self.api_key_env:
            raise ConfigError('지정한 환경변수에서 API 키를 찾을 수 없습니다.')
        return None

    def glossary(self, lang: str) -> dict[str, str]:
        path = self.root / 'glossary/glossary.csv'
        if not path.exists():
            return {}
        with path.open(encoding='utf-8-sig', newline='') as handle:
            rows = csv.DictReader(handle)
            if not {'source', *LANGUAGES}.issubset(rows.fieldnames or []):
                raise ConfigError('용어집 열은 source,zh-CN,zh-TW여야 합니다.')
            return {row['source']: row[lang] for row in rows if row['source'] and row[lang]}

    def agent_config(self, lang: str, glossary: dict):
        from docutranslate.agents.segments_agent import SegmentsTranslateAgentConfig
        from app.diagnostics import library_logger
        self.validate()
        if self.ca_bundle:
            os.environ['SSL_CERT_FILE'] = str(self.ca_path())
        extra = dict(self.extra_body)
        if self.max_tokens:
            extra['max_tokens'] = self.max_tokens
        return SegmentsTranslateAgentConfig(
            base_url=self.base_url.rstrip('/'), model_id=self.model, api_key=self.resolve_key(),
            to_lang=LANGUAGES[lang], temperature=self.temperature, timeout=self.timeout_sec,
            force_json=self.json_mode, extra_body=json.dumps(extra), retry=self.retry,
            concurrent=self.concurrent, rpm=self.rpm, thinking='disable', glossary_dict=glossary,
            custom_prompt='Use Taiwan standard terminology and traditional characters.' if lang == 'zh-TW' else None,
            logger=library_logger(self.root), system_proxy_enable=False,
        )

    def make_agent(self, lang: str):
        from app.reuse_agent import FakeAgent
        self.validate()
        glossary = self.glossary(lang)
        if self.engine == 'fake':
            agent = FakeAgent(lang)
            agent.update_glossary_dict(glossary)
            return agent
        from app.secure_agent import SecureSegmentsAgent
        mapped = self.agent_config(lang, glossary)
        try:
            return SecureSegmentsAgent(mapped,
                                       ca_bundle=str(self.ca_path()) if self.ca_bundle else None,
                                       trust_env_proxy=self.trust_env_proxy)
        except (OSError, ValueError):
            raise ConfigError('인증서 또는 번역기 설정을 확인하세요.') from None
