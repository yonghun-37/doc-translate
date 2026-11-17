import json
import logging

import httpx
import pytest

from app.config import Config
from app.engine import extract
from app.pipeline import Pipeline
from app.reuse_agent import FakeAgent
from tests.test_pipeline import register
from tests.documents import docx_file, pptx_file, xlsx_file


def test_failure_records_safe_type_and_http_diagnosis(tmp_path):
    pipeline = Pipeline(tmp_path, config=Config(root=tmp_path, engine='fake'))
    job = register(pipeline, xlsx_file(tmp_path/'input.xlsx', body='PRIVATE_DOCUMENT'))
    def broken(lang):
        response = httpx.Response(401, request=httpx.Request('POST','https://llm.internal/v1',headers={'Authorization':'Bearer PRIVATE_KEY'}), text='PRIVATE_DOCUMENT PRIVATE_KEY')
        raise httpx.HTTPStatusError('PRIVATE_DOCUMENT PRIVATE_KEY',request=response.request,response=response)
    pipeline.agent_factory = broken
    pipeline.start_translation(job['id'])
    error = pipeline.store.read_status(job['id'])['error']
    assert 'HTTPStatusError' in error and '401' in error and '인증' in error
    logs = (tmp_path/'logs/events.jsonl').read_text()
    failure = [json.loads(line) for line in logs.splitlines() if json.loads(line)['event'] == 'failure'][0]
    assert '401' in failure['message'] and failure['code'] == 'HTTPStatusError'
    assert 'PRIVATE_DOCUMENT' not in error + logs and 'PRIVATE_KEY' not in error + logs


def test_library_warnings_are_logged_without_payload(tmp_path, monkeypatch):
    import app.engine as engine
    pipeline = Pipeline(tmp_path, config=Config(root=tmp_path, engine='fake'))
    source = xlsx_file(tmp_path/'input.xlsx')
    job = register(pipeline, source)
    original = engine.translate
    def noisy(path, agent, **kwargs):
        kwargs['logger'].warning('source PRIVATE_DOCUMENT key PRIVATE_KEY', exc_info=True)
        return original(path,agent,**kwargs)
    monkeypatch.setattr(engine,'translate',noisy)
    pipeline.start_translation(job['id'])
    text = (tmp_path/'logs/library.log').read_text()
    assert 'WARNING' in text
    assert 'PRIVATE_DOCUMENT' not in text and 'PRIVATE_KEY' not in text
    assert pipeline.store.read_status(job['id'])['status'] == 'translated'


def test_docx_extraction_locations_are_aligned_and_human_readable(tmp_path):
    from app.engine import extract_with_locations
    source = docx_file(tmp_path/'input.docx', extra_parts=True)
    texts, locations = extract_with_locations(source)
    assert texts == extract(source)
    where = dict(zip(texts,locations))
    assert where['기존 본문'] == '본문 문단 1'
    assert where['유지 문단'] == '본문 문단 2'
    assert '표 1·1행 1열' in where['표 내용']
    for text, label in [('머리글','머리글'),('바닥글','바닥글'),('각주 내용','각주'),('미주 내용','미주'),('텍스트 상자','텍스트 상자')]:
        assert label in where[text]


def test_pptx_locations_separate_slides_notes_and_master(tmp_path):
    from app.engine import extract_with_locations
    source = pptx_file(tmp_path/'input.pptx')
    texts, locations = extract_with_locations(source)
    assert texts == extract(source)
    assert len(locations) == len(texts)
    assert '슬라이드 1' in locations[texts.index('기존 제목')]
    assert '노트' in locations[texts.index('발표자 노트')]
    assert any('마스터' in where for where in locations)
    assert any('레이아웃' in where for where in locations)


def test_change_locations_keep_repeated_text_positions(tmp_path):
    from docx import Document
    pipeline = Pipeline(tmp_path,config=Config(root=tmp_path,engine='fake'))
    doc = Document()
    for text in ['중복', '중복', '끝']:
        doc.add_paragraph(text)
    original = tmp_path/'old.docx'
    revised = tmp_path/'new.docx'
    doc.save(original)
    doc.paragraphs[1].text = '변경됨'
    doc.save(revised)
    job = register(pipeline, revised, original=original)
    changes = json.loads((pipeline.store.job_dir(job['id'])/'review/changes.json').read_text())
    assert changes == [{'op':'modified','old':'중복','new':'변경됨','where':'본문 문단 2'}]


@pytest.mark.parametrize('kind,inner,label', [
    (httpx.ReadTimeout, TimeoutError, '시간 제한'),
    (httpx.ConnectError, OSError, '연결'),
])
def test_network_diagnosis_keeps_httpx_context_over_low_level_cause(kind, inner, label):
    from app.diagnostics import safe_error
    network = kind('PRIVATE_DOCUMENT')
    network.__cause__ = inner('PRIVATE_KEY')
    outer = RuntimeError('PRIVATE_DOCUMENT PRIVATE_KEY')
    outer.__cause__ = network
    code, message = safe_error(outer)
    assert code == kind.__name__ and label in message
    assert 'PRIVATE_' not in code + message
