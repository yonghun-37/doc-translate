import logging
import os
from pathlib import Path

import pytest

from app.config import Config, ConfigError


def config_at(root, **kwargs):
    return Config(root=root, engine='openai_compatible', base_url='https://llm.internal/v1',
                  model='internal-model', api_key_env='', api_key_file='', **kwargs)


def test_allowlist_denies_before_key_read(tmp_path, monkeypatch):
    config = config_at(tmp_path)
    monkeypatch.setattr(Config, 'resolve_key', lambda _: pytest.fail('차단 전에 키를 읽음'))
    with pytest.raises(ConfigError, match='allowed_hosts'):
        config.make_agent('zh-CN')


@pytest.mark.parametrize('host', ['localhost', '127.0.0.1', '[::1]'])
def test_local_hosts_always_allowed(tmp_path, host):
    config = Config(root=tmp_path, base_url=f'http://{host}:8001/v1', model='local', api_key_env='', api_key_file='')
    config.validate()


def test_legacy_remote_only_adds_selected_host_and_warns(tmp_path, caplog, monkeypatch):
    monkeypatch.delenv('DOC_TRANSLATE_BASE_URL', raising=False)
    path = tmp_path/'legacy.toml'
    path.write_text('[translator]\nengine="openai_compatible"\n[translator.openai_compatible]\nbase_url="https://legacy.internal/v1"\nallow_remote=true\n')
    original = path.read_bytes()
    with caplog.at_level(logging.WARNING):
        config = Config.load(tmp_path, path)
    assert config.allowed_hosts == ['legacy.internal']
    assert 'allow_remote' in caplog.text
    config.base_url = 'https://other.internal/v1'
    with pytest.raises(ConfigError, match='allowed_hosts'):
        config.validate()
    assert path.read_bytes() == original


def test_legacy_false_does_not_allow_remote(tmp_path):
    (tmp_path/'config.toml').write_text('[translator.openai_compatible]\nbase_url="https://remote.internal/v1"\nallow_remote=false\n')
    config = Config.load(tmp_path)
    assert config.allowed_hosts == []
    with pytest.raises(ConfigError, match='allowed_hosts'):
        config.validate()


def test_config_explicit_path_missing_is_error(tmp_path):
    with pytest.raises(ConfigError, match='설정 파일'):
        Config.load(tmp_path, tmp_path/'missing.toml')


def test_ca_path_and_proxy_mapping(tmp_path, monkeypatch):
    monkeypatch.delenv('SSL_CERT_FILE', raising=False)
    ca = tmp_path/'internal.pem'
    import certifi
    ca.write_bytes(Path(certifi.where()).read_bytes())
    config = config_at(tmp_path, allowed_hosts=['llm.internal'], ca_bundle='internal.pem', trust_env_proxy=True)
    mapped = config.agent_config('zh-CN', {})
    assert os.environ['SSL_CERT_FILE'] == str(ca)
    # The subclass owns client construction; upstream insecure proxy mounts stay disabled.
    assert mapped.system_proxy_enable is False
    agent = config.make_agent('zh-CN')
    assert agent.trust_env_proxy is True
    assert agent.ssl_context.verify_mode == __import__('ssl').CERT_REQUIRED
    assert agent.ssl_context.check_hostname is True
    assert mapped.force_json is False


def test_missing_ca_is_clear_error(tmp_path):
    config = config_at(tmp_path, allowed_hosts=['llm.internal'], ca_bundle='missing.pem')
    with pytest.raises(ConfigError, match='인증서'):
        config.validate()


@pytest.mark.parametrize('options', [dict(allowed_hosts='llm.internal'), dict(allowed_hosts=['https://llm.internal']),
    dict(allowed_hosts=['*.internal']), dict(trust_env_proxy='false'), dict(ca_bundle=True)])
def test_bad_security_config(tmp_path, options):
    with pytest.raises(ConfigError):
        config_at(tmp_path, **options).validate()


def test_secure_client_used_at_upstream_request_boundary(tmp_path, monkeypatch):
    import asyncio
    import httpx
    from docutranslate.agents.segments_agent import SegmentsTranslateAgent
    agent = config_at(tmp_path, allowed_hosts=['llm.internal']).make_agent('zh-CN')
    captured = {}
    class Client:
        def __init__(self, **kwargs):
            captured.update(kwargs)
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
    async def request(self, client, data, headers):
        assert isinstance(client, Client)
        return {'choices': []}
    monkeypatch.setattr(httpx, 'AsyncClient', Client)
    monkeypatch.setattr(SegmentsTranslateAgent, '_request_completion_async', request)
    assert asyncio.run(agent._request_completion_async(object(), {}, {})) == {'choices': []}
    assert captured['verify'] is agent.ssl_context
    assert captured['trust_env'] is False
    assert not captured.get('follow_redirects', False)


def test_make_agent_retains_missing_key_diagnostic(tmp_path, monkeypatch):
    monkeypatch.delenv('DOC_TRANSLATE_MISSING_TEST', raising=False)
    config = Config(root=tmp_path, base_url='http://localhost/v1', model='local',
                    api_key_env='DOC_TRANSLATE_MISSING_TEST', api_key_file='')
    with pytest.raises(ConfigError, match='환경변수에서 API 키'):
        config.make_agent('zh-CN')
