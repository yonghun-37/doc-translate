from fastapi.testclient import TestClient
import pytest

from app.cli import main
from app.config import Config
from app.pipeline import Pipeline
from app.web import create_app
from tests.documents import xlsx_file, pptx_file, docx_file
from tests.conftest import client_loop
from tests.test_pipeline import register


@pytest.fixture
def web(tmp_path):
    pipeline = Pipeline(tmp_path / 'data', config=Config(root=tmp_path / 'data', engine='fake'))
    original = xlsx_file(tmp_path / 'original.xlsx')
    revised = xlsx_file(tmp_path / 'revised.xlsx', body='<script>본문</script>')
    job = register(pipeline, revised, original=original)
    with TestClient(create_app(pipeline.store.root, pipeline=pipeline), base_url='http://127.0.0.1:8000',
                    backend_options={'loop_factory': client_loop}) as client:
        yield client, pipeline, job['id']


def test_reject_requires_reason_and_state_transition(web):
    client, pipeline, job_id = web; url = f'/api/jobs/{job_id}'
    assert client.post(url + '/reject', json={'reason': ' '}).status_code == 400
    assert client.post(url + '/reject').status_code == 400
    response = client.post(url + '/reject', json={'reason': '수정 필요', 'by': '검토자'})
    assert response.status_code == 200 and response.json()['reason'] == '수정 필요'
    assert pipeline.store.read_status(job_id)['status'] == 'rejected'
    assert client.post(url + '/reject', json={'reason': '다시'}).status_code == 409
    assert client.delete(url).status_code == 204


@pytest.mark.parametrize('name', ['%2e%2e/config.toml', '%2e%2e/%2e%2e/README.md', 'inputs/revised.xlsx',
    'status.json', 'memory_zh-CN.json', 'review/changes.json', '.work-test/result.xlsx', 'a%5cb.xlsx'])
def test_download_traversal_and_private_artifacts_blocked(web, name):
    client, _, job_id = web
    assert client.get(f'/api/jobs/{job_id}/files/{name}').status_code == 404


def test_output_symlink_and_other_job_files_blocked(web, tmp_path):
    client, pipeline, job_id = web
    client.post(f'/api/jobs/{job_id}/translate')
    state = pipeline.store.read_status(job_id)
    target = pipeline.store.job_dir(job_id) / state['outputs']['zh-CN']
    target.unlink(); target.symlink_to(xlsx_file(tmp_path / 'private.xlsx'))
    assert client.get(f'/api/jobs/{job_id}/files/{target.name}').status_code == 404
    other = register(pipeline, xlsx_file(tmp_path / 'other.xlsx'))
    assert client.get(f"/api/jobs/{other['id']}/files/{target.name}").status_code == 404


def test_delete_checks_origin_and_translating(web):
    client, pipeline, job_id = web; url = f'/api/jobs/{job_id}'
    assert client.delete(url, headers={'Origin': 'https://evil.example'}).status_code == 403
    pipeline.start_translation(job_id, background=True)
    assert client.delete(url).status_code == 409
    assert client.get(url).json()['status'] == 'translating'


def test_failed_retry_and_hidden_partial_outputs(web):
    client, pipeline, job_id = web; url = f'/api/jobs/{job_id}'
    factory = pipeline.agent_factory
    def broken(lang): raise RuntimeError('PRIVATE_KEY')
    pipeline.agent_factory = broken
    assert client.post(url + '/translate').status_code == 202
    detail = client.get(url).json()
    assert detail['status'] == 'failed' and not detail['outputs'] and 'PRIVATE_' not in detail['error']
    pipeline.agent_factory = factory
    assert client.post(url + '/retry').status_code == 202
    assert client.get(url).json()['status'] == 'translated'


@pytest.mark.parametrize('ext,maker', [('docx', docx_file), ('pptx', pptx_file), ('xlsx', xlsx_file)])
def test_format_specific_apis(tmp_path, ext, maker):
    pipeline = Pipeline(tmp_path / 'data', config=Config(root=tmp_path / 'data', engine='fake'))
    job = register(pipeline, maker(tmp_path / f'new.{ext}', body='개정'), original=maker(tmp_path / f'old.{ext}'))
    with TestClient(create_app(pipeline.store.root, pipeline=pipeline), base_url='http://127.0.0.1:8000', backend_options={'loop_factory': client_loop}) as client:
        url = f"/api/jobs/{job['id']}"; detail = client.get(url).json()
        assert detail['changes']
        if ext == 'docx': assert client.get(detail['artifacts']['redline']).status_code == 200
        assert client.get(url + '/sheets').status_code == (200 if ext == 'xlsx' else 404)
        assert client.get(url + '/slides').status_code == (200 if ext == 'pptx' else 404)
        if ext == 'pptx': assert client.get(url + '/slides').json()[0]['slide'] == 1


def test_spa_fallback_and_removed_endpoints(tmp_path):
    pipeline = Pipeline(tmp_path, config=Config(root=tmp_path, engine='fake')); dist = tmp_path / 'dist'
    with TestClient(create_app(tmp_path, pipeline=pipeline, dist_dir=dist), base_url='http://127.0.0.1:8000', backend_options={'loop_factory': client_loop}) as client:
        assert 'npm run build' in client.get('/').text
        (dist / 'assets').mkdir(parents=True)
        (dist / 'index.html').write_text('<html>SPA</html>'); (dist / 'assets/app.js').write_text('const app = 1;')
        for url in ['/new', '/jobs/20261117-090000-abcdef', '/config.toml']:
            assert client.get(url).text == '<html>SPA</html>'
        assert client.get('/assets/app.js').text == 'const app = 1;'
        for url in ['/api/documents', '/api/reviews', '/api/uploads', '/api', '/api/jobs/bad', '/api/jobs/%2e%2e%5csecret', '/assets/%2e%2e/config.toml']:
            assert client.get(url).status_code == 404


def test_original_filenames_with_url_characters_download(web, tmp_path):
    client, pipeline, _ = web
    path = xlsx_file(tmp_path / '문서 #?%&.xlsx'); job = register(pipeline, path)
    client.post(f"/api/jobs/{job['id']}/translate")
    for output in client.get(f"/api/jobs/{job['id']}").json()['outputs']:
        assert client.get(output['url']).status_code == 200


def test_latest_first_listing_and_same_titles(web, tmp_path):
    client, pipeline, first_id = web
    source = xlsx_file(tmp_path / 'revised.xlsx')
    second = register(pipeline, source)
    items = client.get('/api/jobs').json()
    assert [item['id'] for item in items] == [second['id'], first_id]
    assert items[0]['title'] == items[1]['title']


def test_cli_serve_custom_config_and_removed_commands(tmp_path, monkeypatch):
    import app.cli as cli
    custom = tmp_path / 'custom.toml'; custom.write_text('[translator]\nengine="fake"\n')
    default = tmp_path / 'config.toml'; default.write_text('broken = [')
    started = []
    monkeypatch.setattr(cli.uvicorn, 'run', lambda app, **kwargs: started.append((kwargs, app.state.max_upload_bytes, app.state.pipeline.config.engine)))
    common = ['--root', str(tmp_path), '--config', str(custom)]
    assert main([*common, 'serve', '--port', '8123', '--max-upload-mb', '7', '--allowed-host', 'proxy.internal']) == 0
    assert started == [({'host': '127.0.0.1', 'port': 8123}, 7 * 1024 * 1024, 'fake')]
    assert default.read_text() == 'broken = ['
    for options in [['--host', '0.0.0.0'], ['--max-upload-mb', '0'], ['--allowed-host', '*.example']]:
        assert main([*common, 'serve', *options]) == 1
    for name in ['watch', 'process', 'approve', 'reject', 'retry', 'status']:
        with pytest.raises(SystemExit): cli.parser().parse_args([name])


def test_check_translator_reports_current_mode_elapsed_and_usage_without_probe(tmp_path, monkeypatch, capsys):
    import app.cli as cli
    from app.reuse_agent import FakeAgent
    (tmp_path/'config.toml').write_text('[translator]\nengine="fake"\n')
    calls = []
    class StatsAgent(FakeAgent):
        def send_segments(self, values, chunk_size):
            calls.append(self.lang)
            return super().send_segments(values, chunk_size)
        def get_full_stats(self):
            return {'reasoning_tokens': 147, 'unresolved_errors': 0}
    monkeypatch.setattr(cli.Config,'make_agent',lambda self,lang: StatsAgent(lang))
    assert main(['check-translator','--root',str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert 'json_mode=false' in out and '소요 시간' in out and '추론 토큰: 147' in out
    assert calls == ['zh-CN','zh-TW']


def test_extra_proxy_host_is_trusted_only_when_configured(tmp_path):
    pipeline = Pipeline(tmp_path, config=Config(root=tmp_path, engine='fake'))
    host = 'yh-lab.example.ts.net'
    with TestClient(create_app(tmp_path, pipeline=pipeline), base_url=f'https://{host}',
                    backend_options={'loop_factory': client_loop}) as client:
        assert client.get('/api/jobs').status_code == 400
    with TestClient(create_app(tmp_path, pipeline=pipeline, extra_hosts=[host]), base_url=f'https://{host}',
                    backend_options={'loop_factory': client_loop}) as client:
        assert client.get('/api/jobs').status_code == 200
        r = client.post('/api/jobs/missing/reject', json={'reason': 'r'}, headers={'origin': 'https://evil.example'})
        assert r.status_code == 403


@pytest.mark.parametrize('filename', ['.초안.xlsx', 'a' * 230 + '.xlsx'])
def test_free_filename_output_remains_downloadable(web, tmp_path, filename):
    client, pipeline, _ = web
    job = register(pipeline, xlsx_file(tmp_path / filename))
    assert client.post(f"/api/jobs/{job['id']}/translate").status_code == 202
    for output in client.get(f"/api/jobs/{job['id']}").json()['outputs']:
        assert client.get(output['url']).status_code == 200
