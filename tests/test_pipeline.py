from concurrent.futures import ThreadPoolExecutor
import json
import threading

import pytest

from app.config import Config
from app.engine import extract, translate
from app.pipeline import Pipeline, StateError, InvalidUpload
from app.reuse_agent import FakeAgent, ReuseAgent
from app.storage import read_json
from tests.documents import docx_file, xlsx_file, pptx_file


@pytest.fixture
def pipeline(tmp_path):
    return Pipeline(tmp_path / 'data', config=Config(root=tmp_path / 'data', engine='fake'))


def register(pipeline, revised, **files):
    return pipeline.upload({role: (path, path.name) for role, path in {'revised': revised, **files}.items()})


@pytest.mark.parametrize('ext,maker', [('docx', docx_file), ('xlsx', xlsx_file), ('pptx', pptx_file)])
@pytest.mark.parametrize('bases', ['both', 'one', 'none', 'no-original'])
def test_job_translation_reuses_uploaded_bases_per_language(pipeline, tmp_path, ext, maker, bases):
    original = maker(tmp_path / f'original.{ext}')
    revised = maker(tmp_path / f'수정본.{ext}', body='새로운 문장')
    files = {'original': original} if bases != 'no-original' else {}
    for lang in ('zh-CN', 'zh-TW'):
        if bases in {'both', 'no-original'} or (bases == 'one' and lang == 'zh-CN'):
            base = tmp_path / f'{lang}.{ext}'
            base.write_bytes(translate(original, ReuseAgent({}, FakeAgent(lang))))
            files[f'base_{lang}'] = base
    agents = []
    def factory(lang):
        agent = FakeAgent(lang); agents.append(agent); return agent
    pipeline.agent_factory = factory
    pending = register(pipeline, revised, **files)
    assert pending['status'] == 'pending' and not agents and not pending['outputs']
    folder = pipeline.store.job_dir(pending['id'])
    inputs = {path.name: path.read_bytes() for path in (folder / 'inputs').iterdir()}
    review = {path.name: path.read_bytes() for path in (folder / 'review').iterdir()}
    assert bool(read_json(folder / 'review/changes.json')) == (bases != 'no-original')
    state = pipeline.start_translation(pending['id'], by=' 검토자 ')
    assert state['status'] == 'translated' and state['decided_by'] == '검토자'
    plans = read_json(folder / 'review/plan.json')
    for lang, agent in zip(('zh-CN', 'zh-TW'), agents):
        stats = state['stats'][lang]
        assert stats == plans[lang]
        sent = [text for batch in agent.calls for text in batch]
        if bases == 'both' or (bases == 'one' and lang == 'zh-CN'):
            assert sent == ['새로운 문장'] and stats['reused'] > 0 and stats['translated'] == 1
        else:
            assert '새로운 문장' in sent and stats['reused'] == 0 and stats['translated'] > 1
        assert state['outputs'][lang] == f'output/수정본_{lang}.{ext}'
        assert (folder / state['outputs'][lang]).is_file()
    assert inputs == {path.name: path.read_bytes() for path in (folder / 'inputs').iterdir()}
    assert review == {path.name: path.read_bytes() for path in (folder / 'review').iterdir()}


def test_failure_cleans_outputs_and_retry_keeps_inputs_memory(pipeline, tmp_path):
    path = xlsx_file(tmp_path / 'input.xlsx', body='PRIVATE_BODY')
    job = register(pipeline, path)
    class Broken(FakeAgent):
        def send_segments(self, *args): raise RuntimeError('PRIVATE_BODY PRIVATE_KEY')
    pipeline.agent_factory = lambda lang: Broken(lang) if lang == 'zh-TW' else FakeAgent(lang)
    state = pipeline.start_translation(job['id'])
    assert state['status'] == 'failed' and state['outputs'] == {} and state['stats'] == {}
    folder = pipeline.store.job_dir(job['id'])
    assert not (folder / 'output').exists() and not list(folder.glob('.work-*'))
    assert 'PRIVATE_' not in state['error'] + pipeline.store.path('logs/events.jsonl').read_text()
    pipeline.agent_factory = FakeAgent
    assert pipeline.retry(job['id'])['status'] == 'translated'
    assert (folder / 'inputs/revised.xlsx').read_bytes() == path.read_bytes()


def test_reservation_rejection_deletion_and_invalid_transitions(pipeline, tmp_path):
    path = xlsx_file(tmp_path / 'input.xlsx')
    job = register(pipeline, path); job_id = job['id']
    with pytest.raises(StateError): pipeline.reject(job_id, ' ')
    assert pipeline.start_translation(job_id, background=True)['status'] == 'translating'
    for fn in (pipeline.start_translation, pipeline.retry, pipeline.delete):
        with pytest.raises(StateError): fn(job_id)
    with pytest.raises(StateError): pipeline.reject(job_id, '거절')
    pipeline.translate(job_id)
    with pytest.raises(StateError): pipeline.translate(job_id)
    pipeline.delete(job_id)
    assert not pipeline.store.job_dir(job_id).exists()
    other = register(pipeline, path)
    assert pipeline.reject(other['id'], ' 반려 ', ' 검토자 ')['reason'] == '반려'
    with pytest.raises(StateError): pipeline.start_translation(other['id'])
    pipeline.delete(other['id'])
    assert pipeline.store.statuses() == []


def test_delete_while_real_translation_lock_held_rejects_immediately(pipeline, tmp_path):
    job = register(pipeline, xlsx_file(tmp_path / 'input.xlsx'))
    started, release = threading.Event(), threading.Event()
    def factory(lang):
        started.set(); assert release.wait(5); return FakeAgent(lang)
    pipeline.agent_factory = factory
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(pipeline.start_translation, job['id'])
        try:
            assert started.wait(5)
            with pytest.raises(StateError): pipeline.delete(job['id'])
        finally:
            release.set()
        assert future.result()['status'] == 'translated'


def test_prepare_failure_and_interrupt_publish_nothing(pipeline, tmp_path, monkeypatch):
    path = xlsx_file(tmp_path / 'input.xlsx')
    for error in (RuntimeError('PRIVATE_KEY'), KeyboardInterrupt()):
        def broken(*args): raise error
        monkeypatch.setattr(pipeline, '_prepare', broken)
        with pytest.raises(InvalidUpload if isinstance(error, Exception) else KeyboardInterrupt):
            register(pipeline, path)
        assert not list(pipeline.store.path('jobs').iterdir())
        assert not list(pipeline.store.path('logs/.uploads').iterdir())
        assert path.exists()


def test_translation_interrupt_allows_retry(pipeline, tmp_path):
    job = register(pipeline, xlsx_file(tmp_path / 'input.xlsx'))
    def interrupted(lang): raise KeyboardInterrupt()
    pipeline.agent_factory = interrupted
    with pytest.raises(KeyboardInterrupt): pipeline.start_translation(job['id'])
    assert pipeline.store.read_status(job['id'])['status'] == 'failed'
    restarted = Pipeline(pipeline.store.root, config=pipeline.config)
    assert restarted.retry(job['id'])['status'] == 'translated'


def test_two_simultaneous_jobs_are_independent_and_same_names_allowed(pipeline, tmp_path):
    other = Pipeline(pipeline.store.root, config=pipeline.config)
    paths = [xlsx_file(tmp_path / f'{i}.xlsx') for i in range(2)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = list(pool.map(lambda pair: register(*pair), zip([pipeline, other], paths)))
    assert jobs[0]['id'] != jobs[1]['id'] and len(pipeline.store.statuses()) == 2
    pipeline.reject(jobs[0]['id'], '반려')
    assert pipeline.start_translation(jobs[1]['id'])['status'] == 'translated'


def test_registration_is_not_visible_until_completely_prepared(pipeline, tmp_path, monkeypatch):
    path = xlsx_file(tmp_path / 'input.xlsx')
    prepare = pipeline._prepare
    def inspect(state, folder):
        prepare(state, folder)
        assert pipeline.store.statuses() == []
        assert (folder / 'inputs/revised.xlsx').is_file()
    monkeypatch.setattr(pipeline, '_prepare', inspect)
    job = register(pipeline, path)
    assert pipeline.store.statuses()[0]['id'] == job['id']


def test_registration_never_validates_or_calls_llm(pipeline, tmp_path, monkeypatch):
    def forbidden(*args, **kwargs): pytest.fail('업로드에서 LLM 설정 접근')
    monkeypatch.setattr(Config, 'validate', forbidden)
    monkeypatch.setattr(Config, 'make_agent', forbidden)
    pipeline.agent_factory = forbidden
    assert register(pipeline, xlsx_file(tmp_path / 'input.xlsx'))['status'] == 'pending'


def test_job_publish_failure_removes_staging(pipeline, tmp_path, monkeypatch):
    import app.pipeline as module
    original_replace = module.os.replace
    def fail_job(source, destination):
        if destination.parent == pipeline.store.path('jobs'):
            raise OSError('PRIVATE_PATH')
        return original_replace(source, destination)
    monkeypatch.setattr(module.os, 'replace', fail_job)
    with pytest.raises(InvalidUpload): register(pipeline, xlsx_file(tmp_path / 'new.xlsx'))
    assert pipeline.store.statuses() == []
    assert not list(pipeline.store.path('jobs').iterdir())
    assert not list(pipeline.store.path('logs/.uploads').iterdir())
