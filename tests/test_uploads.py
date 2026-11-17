import asyncio

from fastapi.testclient import TestClient
import httpx
import pytest

from app.config import Config
from app.pipeline import Pipeline
from app.web import create_app
from tests.conftest import client_loop
from tests.documents import docx_file, pptx_file, xlsx_file


@pytest.fixture
def web(tmp_path):
    root = tmp_path / 'data'
    pipeline = Pipeline(root, config=Config(root=root, engine='fake'))
    with TestClient(create_app(root, pipeline=pipeline, max_upload_mb=1), base_url='http://127.0.0.1:8000',
                    backend_options={'loop_factory': client_loop}) as client:
        yield client, pipeline


def post(client, content, *, name='자유로운 이름.xlsx', **kwargs):
    return client.post('/api/jobs', files={'revised': (name, content)}, **kwargs)


def clean(pipeline):
    assert not list(pipeline.store.path('logs/.uploads').glob('*'))


def empty(pipeline):
    assert not list(pipeline.store.path('jobs').iterdir())
    clean(pipeline)


@pytest.mark.parametrize('ext,maker', [('docx', docx_file), ('xlsx', xlsx_file), ('pptx', pptx_file)])
def test_pending_new_job_metadata_then_explicit_translation(web, tmp_path, ext, maker):
    client, pipeline = web
    content = maker(tmp_path / f'source.{ext}').read_bytes()
    response = post(client, content, name=f'C:\\fakepath\\초안_rev999.{ext.upper()}', data={'by': ' 홍길동 '})
    assert response.status_code == 201, response.text
    state = response.json(); job_id = state['id']; url = f'/api/jobs/{job_id}'
    assert state['status'] == 'pending' and state['changes'] == []
    assert state['counts'] == {'added': 0, 'removed': 0, 'modified': 0}
    assert state['decided_at'] is None and state['decided_by'] is None
    assert state['uploaded_by'] == '홍길동' and state['title'] == f'초안_rev999.{ext.upper()}'
    assert state['files'] == {'revised': f'초안_rev999.{ext.upper()}'}
    assert state['outputs'] == [] and state['artifacts'] == {} and state['alignment'] == {}
    assert client.get(url).json() == state
    assert client.get('/api/jobs').json()[0]['id'] == job_id
    assert set(state['plan']) == {'zh-CN', 'zh-TW'}
    assert (pipeline.store.job_dir(job_id) / f'inputs/revised.{ext}').read_bytes() == content
    clean(pipeline)
    response = client.post(url + '/translate', json={'by': '검토자'})
    assert response.status_code == 202 and response.json()['status'] == 'translating'
    result = client.get(url).json()
    assert result['status'] == 'translated' and len(result['outputs']) == 2
    assert result['decided_by'] == '검토자'
    assert result['stats'] == result['plan']
    for output in result['outputs']:
        assert client.get(output['url']).status_code == 200
    assert client.post(url + '/translate').status_code == 409
    assert client.post(url + '/retry').status_code == 409
    assert client.delete(url).status_code == 204
    assert client.get(url).status_code == 404 and client.get('/api/jobs').json() == []
    assert client.get(result['outputs'][0]['url']).status_code == 404
    empty(pipeline)


@pytest.mark.parametrize('case', ['unsupported', 'corrupt', 'wrong-package', 'oversize', 'exact-limit'])
def test_invalid_file_and_size_leave_no_files(web, tmp_path, case):
    client, pipeline = web
    content = xlsx_file(tmp_path / 'source.xlsx').read_bytes(); name = 'source.xlsx'
    if case == 'unsupported': name = 'source.xlsm'
    elif case == 'corrupt': content = b'broken'
    elif case == 'wrong-package': name = 'source.docx'
    else: content = b'x' * (1024 * 1024 + (case == 'oversize'))
    response = post(client, content, name=name)
    assert response.status_code == (413 if case == 'oversize' else 400)
    empty(pipeline)


@pytest.mark.parametrize('role', ['original', 'base_zh_cn', 'base_zh_tw'])
def test_extension_mismatch_all_optional_roles_rejected(web, tmp_path, role):
    client, pipeline = web
    response = client.post('/api/jobs', files={'revised': ('x.xlsx', xlsx_file(tmp_path / 'x.xlsx').read_bytes()),
        role: ('b.docx', docx_file(tmp_path / 'b.docx').read_bytes())})
    assert response.status_code == 400 and '확장자' in response.json()['detail']
    empty(pipeline)


def test_same_original_and_revised_rejected(web, tmp_path):
    client, pipeline = web
    content = xlsx_file(tmp_path / 'x.xlsx').read_bytes()
    response = client.post('/api/jobs', files={key: (f'{key}.xlsx', content) for key in ('original', 'revised')})
    assert response.status_code == 400 and '동일' in response.json()['detail']
    empty(pipeline)


def test_all_four_files_each_have_own_size_budget(web, tmp_path):
    from app.engine import translate
    from app.reuse_agent import FakeAgent, ReuseAgent
    client, pipeline = web
    original = xlsx_file(tmp_path / 'old.xlsx'); revised = xlsx_file(tmp_path / 'new.xlsx', body='개정')
    def padded(content):
        from io import BytesIO
        from zipfile import ZipFile
        buffer = BytesIO(content)
        with ZipFile(buffer, 'a') as archive:
            archive.writestr('padding.bin', b'x' * 400_000)
        return buffer.getvalue()
    files = {'original': ('원본.xlsx', padded(original.read_bytes())), 'revised': ('수정본.xlsx', padded(revised.read_bytes()))}
    for role, lang in [('base_zh_cn', 'zh-CN'), ('base_zh_tw', 'zh-TW')]:
        files[role] = (f'{lang}.xlsx', padded(translate(original, ReuseAgent({}, FakeAgent(lang)))))
    response = client.post('/api/jobs', files=files, data={'title': ' 독립 작업 '})
    assert response.status_code == 201, response.text
    job = response.json()
    assert job['title'] == '독립 작업' and len(job['files']) == 4
    assert job['alignment']['zh-CN']['matched'] > 0
    assert job['plan']['zh-CN']['translated'] == 1
    assert client.get(f"/api/jobs/{job['id']}/sheets").json()
    clean(pipeline)


@pytest.mark.parametrize('headers', [{'Origin': 'https://evil.example'}, {'Origin': 'https://127.0.0.1:8000'}, {'Sec-Fetch-Site': 'cross-site'}, {'Origin': 'null'}])
def test_other_origin_forbidden_with_security_headers(web, tmp_path, headers):
    client, pipeline = web
    response = post(client, xlsx_file(tmp_path / 'x.xlsx').read_bytes(), headers=headers)
    assert response.status_code == 403
    assert response.headers['X-Content-Type-Options'] == 'nosniff'
    assert 'Content-Security-Policy' in response.headers
    empty(pipeline)


def test_prepare_failure_is_safe_and_rolls_back(web, tmp_path, monkeypatch):
    client, pipeline = web
    def broken(*args): raise RuntimeError('PRIVATE_BODY PRIVATE_KEY')
    monkeypatch.setattr(pipeline, '_prepare', broken)
    response = post(client, xlsx_file(tmp_path / 'x.xlsx').read_bytes())
    assert response.status_code == 400 and 'PRIVATE_' not in response.text
    empty(pipeline)


@pytest.mark.parametrize('data', [{'extra': 'bad'}, {'by': 'x' * 201}, {'title': 'x' * 241}])
def test_invalid_text_fields(web, tmp_path, data):
    client, pipeline = web
    assert post(client, xlsx_file(tmp_path / 'x.xlsx').read_bytes(), data=data).status_code == 400
    empty(pipeline)


@pytest.mark.parametrize('case', ['missing-revised', 'duplicate', 'unknown', 'too-many', 'wrong-field-type'])
def test_invalid_file_fields(web, tmp_path, case):
    client, pipeline = web
    content = xlsx_file(tmp_path / 'x.xlsx').read_bytes()
    names = {'missing-revised': ['original'], 'duplicate': ['revised', 'revised'],
             'unknown': ['revised', 'unknown'], 'too-many': ['revised', 'original', 'base_zh_cn', 'base_zh_tw', 'extra'],
             'wrong-field-type': ['revised', 'title']}[case]
    response = client.post('/api/jobs', files=[(name, ('x.xlsx', content)) for name in names])
    assert response.status_code == 400
    empty(pipeline)


def test_disconnect_closes_and_removes_partial_upload(web):
    from starlette.requests import ClientDisconnect
    client, pipeline = web
    async def body():
        yield b'--test\r\nContent-Disposition: form-data; name="revised"; filename="x.xlsx"\r\n\r\npartial'
        raise ClientDisconnect()
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=client.app), base_url='http://127.0.0.1:8000') as api:
            await api.post('/api/jobs', content=body(), headers={'Content-Type': 'multipart/form-data; boundary=test'})
    with pytest.raises(ClientDisconnect): asyncio.run(run(), loop_factory=client_loop)
    empty(pipeline)


def test_stream_stops_before_reading_remainder(web):
    client, pipeline = web; reads = []
    async def body():
        yield b'--test\r\nContent-Disposition: form-data; name="revised"; filename="large.xlsx"\r\n\r\n'
        for i in range(100):
            reads.append(i); yield b'x' * (64 * 1024)
        yield b'\r\n--test--\r\n'
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=client.app), base_url='http://127.0.0.1:8000') as api:
            return await api.post('/api/jobs', content=body(), headers={'Content-Type': 'multipart/form-data; boundary=test'})
    response = asyncio.run(run(), loop_factory=client_loop)
    assert response.status_code == 413 and len(reads) == 17
    empty(pipeline)


@pytest.mark.parametrize('body', [b'broken', b'--test\r\nContent-Disposition: form-data; name="revised"; filename="x.xlsx"\r\n\r\npartial'])
def test_truncated_multipart_is_cleaned(web, body):
    client, pipeline = web
    assert client.post('/api/jobs', content=body, headers={'Content-Type': 'multipart/form-data; boundary=test'}).status_code == 400
    empty(pipeline)


def test_total_request_limit_includes_multipart_framing(web):
    client, pipeline = web
    # A single oversized header cannot bypass the aggregate streaming limit.
    body = b'--test\r\nX-Padding: ' + b'a' * (4 * 1024 * 1024 + 65536)
    assert client.post('/api/jobs', content=body, headers={'Content-Type': 'multipart/form-data; boundary=test'}).status_code == 413
    empty(pipeline)


@pytest.mark.parametrize('role', ['revised', 'original', 'base_zh_cn', 'base_zh_tw'])
def test_valid_zip_with_corrupt_office_xml_is_rejected_and_cleaned(web, tmp_path, role):
    from tests.documents import rewrite_zip
    client, pipeline = web
    valid = xlsx_file(tmp_path / 'valid.xlsx')
    broken = xlsx_file(tmp_path / 'broken.xlsx')
    rewrite_zip(broken, {'xl/workbook.xml': b'<broken'})
    files = {'revised': ('new.xlsx', valid.read_bytes()), role: ('broken.xlsx', broken.read_bytes())}
    response = client.post('/api/jobs', files=files)
    assert response.status_code == 400
    empty(pipeline)


def test_four_file_upload_enforces_limit_on_later_file(web, tmp_path):
    client, pipeline = web
    valid = xlsx_file(tmp_path / 'valid.xlsx').read_bytes()
    response = client.post('/api/jobs', files=[('revised', ('new.xlsx', valid)),
        ('base_zh_tw', ('large.xlsx', b'x' * (1024 * 1024 + 1)))])
    assert response.status_code == 413
    empty(pipeline)
