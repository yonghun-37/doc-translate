import json
from pathlib import Path

import pytest

from app.config import Config, ConfigError, parse_key
from app.reuse_agent import FakeAgent, ReuseAgent, TranslationError
from app.storage import Storage
from app.inputs import display_filename
from app.storage import safe_job_id


@pytest.mark.parametrize('name', ['a.docx', '문서 #?%.xlsx', '발표.PPTX'])
def test_free_filename(name):
    assert display_filename(name) == name


@pytest.mark.parametrize('name', ['', 'wrong.xlsm', 'a\x00.docx', 'x' * 241 + '.docx'])
def test_invalid_filename(name):
    with pytest.raises(ValueError): display_filename(name)


@pytest.mark.parametrize('job_id', ['../escape', '20261117-090000-abcdef/..', 'wrong', '20261117-090000-ABCDEG'])
def test_invalid_job_id(job_id):
    with pytest.raises(ValueError): safe_job_id(job_id)


def test_reuse_deduplicates_and_preserves_order():
    inner = FakeAgent('zh-CN')
    sent = []
    agent = ReuseAgent({'기존': '旧'}, inner, sent)
    values = ['기존', '새 내용', '12345', '3.5%', '10 kg', '  ', '새 내용', '기존']
    assert agent.send_segments(values, 1000) == ['旧', '[zh-CN] 새 내용', '12345', '3.5%', '10 kg', '  ', '[zh-CN] 새 내용', '旧']
    assert sent == ['새 내용']
    assert inner.calls == [['새 내용']]
    assert agent.memory == dict(zip(values, agent.send_segments(values, 1000)))
    agent.update_glossary_dict({'설계서': '设计书'})
    assert inner.glossary == {'설계서': '设计书'}


@pytest.mark.parametrize('result', [[], [None], [''], ['a','b']])
def test_bad_agent_result(result):
    class Broken(FakeAgent):
        def send_segments(self, segments, chunk_size):
            return result
    with pytest.raises(TranslationError):
        ReuseAgent({}, Broken('zh-CN')).send_segments(['본문'], 100)


def test_partial_failure_is_not_success():
    class Partial(FakeAgent):
        def get_full_stats(self):
            return {'unresolved_errors': 1}
    with pytest.raises(TranslationError):
        ReuseAgent({}, Partial('zh-CN')).send_segments(['본문'], 100)


@pytest.mark.parametrize('value', ['thehiveapi:dummy-secret', 'KEY=dummy-secret', 'export KEY="dummy-secret"', '# comment\n\ndummy-secret'])
def test_key_parser(value):
    assert parse_key(value) == 'dummy-secret'


def test_config_mapping_and_env_precedence(tmp_path, monkeypatch):
    root = tmp_path / 'repo'
    root.mkdir()
    keyfile = tmp_path / 'dummy-key'
    keyfile.write_text('thehiveapi:dummy-file-key')
    (root / 'config.toml').write_text(f'''[translator]
engine = "openai_compatible"
[translator.openai_compatible]
base_url = "http://localhost:1234/v1"
model = "local"
api_key_env = "TEST_DOC_KEY"
api_key_file = "{keyfile}"
allow_remote = false
temperature = 0.2
max_tokens = 1234
timeout_sec = 23
json_mode = true
retry = 5
concurrent = 2
rpm = 10
extra_body = {{top_p = 0.8}}
''')
    monkeypatch.delenv('TEST_DOC_KEY', raising=False)
    monkeypatch.delenv('DOC_TRANSLATE_BASE_URL', raising=False)
    monkeypatch.delenv('DOC_TRANSLATE_MODEL', raising=False)
    config = Config.load(root)
    mapped = config.agent_config('zh-TW', {'설계서': '設計書'})
    assert mapped.api_key == 'dummy-file-key'
    assert mapped.base_url == 'http://localhost:1234/v1'
    assert mapped.model_id == 'local'
    assert mapped.to_lang == '繁體中文（台灣）'
    assert mapped.timeout == 23 and mapped.temperature == 0.2
    assert mapped.force_json and mapped.thinking == 'disable'
    assert (mapped.retry, mapped.concurrent, mapped.rpm) == (5, 2, 10)
    assert json.loads(mapped.extra_body) == {'top_p': 0.8, 'max_tokens': 1234}
    assert mapped.glossary_dict == {'설계서': '設計書'}
    monkeypatch.setenv('TEST_DOC_KEY', 'dummy-env-key')
    keyfile.unlink()
    monkeypatch.setenv('DOC_TRANSLATE_MODEL', 'override')
    mapped = Config.load(root).agent_config('zh-CN', {})
    assert mapped.api_key == 'dummy-env-key' and mapped.model_id == 'override'
    assert mapped.to_lang == '简体中文'


def test_remote_guard_before_key_read(tmp_path, monkeypatch):
    config = Config(root=tmp_path, allow_remote=False, api_key_file='/never/read')
    def denied(*args, **kwargs):
        pytest.fail('가드 전에 키를 읽음')
    monkeypatch.setattr(Path, 'read_text', denied)
    with pytest.raises(ConfigError, match='원격'):
        config.agent_config('zh-CN', {})


def test_key_inside_root_rejected(tmp_path):
    config = Config(root=tmp_path, base_url='http://localhost/v1', api_key_env='', api_key_file=str(tmp_path/'key'))
    with pytest.raises(ConfigError, match='저장소'):
        config.agent_config('zh-CN', {})


def test_missing_key_rejected(tmp_path, monkeypatch):
    monkeypatch.delenv('MISSING_DOC_KEY', raising=False)
    config = Config(root=tmp_path, base_url='http://localhost/v1', api_key_env='MISSING_DOC_KEY', api_key_file='')
    with pytest.raises(ConfigError, match='키'):
        config.agent_config('zh-CN', {})


def test_atomic_status_and_paths(tmp_path):
    store = Storage(tmp_path)
    state = {'id': '20261117-090000-abcdef', 'status': 'pending'}
    store.save_status(state)
    assert store.read_status(state['id']) == state
    assert json.loads((tmp_path/'logs/events.jsonl').read_text())['status'] == 'pending'
    with pytest.raises(ValueError):
        store.job_dir('../escape')



@pytest.mark.parametrize('value,expected', [
    ('thehiveapi:opaque-secret==','opaque-secret=='),
    ('KEY="opaque-secret=="','opaque-secret=='),
    ('opaque-secret==','opaque-secret=='),
])
def test_key_parser_preserves_equals(value,expected):
    assert parse_key(value)==expected


@pytest.mark.parametrize('field,value', [('allow_remote','false'),('json_mode','false'),('retry',True),
                                        ('timeout_sec','180'),('concurrent',0)])
def test_config_rejects_wrong_types(tmp_path,field,value):
    config=Config(root=tmp_path,**{field:value})
    with pytest.raises(ConfigError):
        config.validate()


def test_units_and_scientific_numbers_are_not_sent():
    inner=FakeAgent('zh-CN')
    values=['kg','mm²','10 kg/m³','1e3','-2.5E-4','설계서','new']
    result=ReuseAgent({},inner).send_segments(values,1000)
    assert result[:5]==values[:5]
    assert inner.calls==[['설계서','new']]
