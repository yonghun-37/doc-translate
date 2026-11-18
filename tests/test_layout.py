import json
import os
from pathlib import Path
import signal
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor

from docx import Document
from fastapi.testclient import TestClient
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill
from pptx import Presentation
from pptx.util import Inches
import pytest

from app import grid, render
from app.config import Config, ConfigError, RenderConfig
from app.diff.xlsx import compare_sheets
from app.pipeline import Pipeline
from app.progress import Progress
from app.reuse_agent import FakeAgent, ReuseAgent, TranslationError
from app.slide_layout import overlays
from app.storage import read_json, write_json
from app.web import create_app
from tests.conftest import client_loop
from tests.documents import docx_file, pptx_file
from tests.test_pipeline import register


def tiny_pdf(path, texts=('NewOld',)):
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>', b'', b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>']
    kids = []
    for text in texts:
        page_id = len(objects) + 1
        kids.append(f'{page_id} 0 R')
        stream = f'BT /F1 18 Tf 30 160 Td ({text}) Tj ET'.encode()
        objects.extend([f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] /Resources << /Font << /F1 3 0 R >> >> /Contents {page_id+1} 0 R >>'.encode(),
                        f'<< /Length {len(stream)} >>\nstream\n'.encode() + stream + b'\nendstream'])
    objects[1] = f'<< /Type /Pages /Kids [{" ".join(kids)}] /Count {len(kids)} >>'.encode()
    content, offsets = b'%PDF-1.4\n', [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(content)); content += f'{index} 0 obj\n'.encode() + obj + b'\nendobj\n'
    start = len(content)
    content += f'xref\n0 {len(offsets)}\n0000000000 65535 f \n'.encode()
    content += b''.join(f'{offset:010d} 00000 n \n'.encode() for offset in offsets[1:])
    content += f'trailer << /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n'.encode()
    path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(content)
    return path


@pytest.fixture
def pipeline(tmp_path):
    return Pipeline(tmp_path / 'data', config=Config(root=tmp_path / 'data', engine='fake'))


@pytest.fixture
def fake_renderer(monkeypatch):
    monkeypatch.setattr(render, 'find_soffice', lambda config: Path('/fake/soffice'))
    def convert(source, destination, *args):
        return tiny_pdf(destination / (source.stem + '.pdf'))
    monkeypatch.setattr(render, 'convert', convert)


def test_config_render_progress_defaults_and_validation(tmp_path):
    config = Config.load(tmp_path)
    assert config.progress_batch == 40 and config.render == RenderConfig()
    path = tmp_path / 'settings.toml'
    path.write_text('[render]\nsoffice="/custom/soffice"\ntimeout_sec=12\nmax_pages=3\n[translator.openai_compatible]\nprogress_batch=2\n')
    loaded = Config.load(tmp_path, path)
    assert loaded.render.timeout_sec == 12 and loaded.render.max_pages == 3 and loaded.progress_batch == 2
    for bad in ('0', '-1', 'true', '"bad"'):
        path.write_text(f'[render]\nmax_pages={bad}\n')
        with pytest.raises(ConfigError): Config.load(tmp_path, path)
        path.write_text(f'[translator.openai_compatible]\nprogress_batch={bad}\n')
        with pytest.raises(ConfigError): Config.load(tmp_path, path)


def test_executable_precedence_and_shell_free_timeout(tmp_path, monkeypatch):
    env, configured = tmp_path / 'env soffice', tmp_path / 'config soffice'
    for path in (env, configured): path.touch(); path.chmod(0o700)
    monkeypatch.setenv('DOC_TRANSLATE_SOFFICE', str(env))
    config = RenderConfig(soffice=str(configured), timeout_sec=1)
    assert render.find_soffice(config) == env
    monkeypatch.delenv('DOC_TRANSLATE_SOFFICE')
    assert render.find_soffice(config) == configured
    calls, killed = [], []
    class Process:
        pid = 12345
        def __init__(self, args, **kwargs): calls.append((args, kwargs))
        def wait(self, timeout=None):
            if timeout: raise subprocess.TimeoutExpired('soffice', timeout)
            return -9
    monkeypatch.setattr(render.subprocess, 'Popen', Process)
    monkeypatch.setattr(render.os, 'killpg', lambda pid, sig: killed.append((pid, sig)))
    with pytest.raises(render.RenderTimeout): render.convert(tmp_path / 'source;ignored.docx', tmp_path / 'pdf', configured, config, tmp_path)
    assert killed == [(12345, signal.SIGKILL)]
    assert calls[0][1]['start_new_session'] and 'shell' not in calls[0][1]
    assert calls[0][0][-1].endswith('source;ignored.docx')
    assert not list((tmp_path / '.lo-profile').iterdir())


def test_pdfium_size_limit_and_text(tmp_path):
    pages, texts, total = render.rasterize(tiny_pdf(tmp_path / 'test.pdf', ['one', 'two', 'three']), tmp_path, 'redline', 2)
    assert total == 3 and len(pages) == 2 and texts[1] == 'two'
    assert max(pages[0]['width'], pages[0]['height']) == 1600
    assert (tmp_path / pages[0]['name']).read_bytes().startswith(b'\x89PNG')
    assert not (tmp_path / 'redline-003.png').exists()


def test_sequential_repeated_paragraph_locations_and_non_body():
    changes = [{'where': f'본문 문단 {i}', 'old': '', 'new': '같은 문구'} for i in (1, 2)]
    changes += [{'where': '머리글 문단 1', 'old': '', 'new': '같은 문구'}, {'where': '본문 문단 3', 'old': '', 'new': '없음'}]
    render.locate_pages(changes, ['같은\n문구', '같은 문구'])
    assert [c.get('page') for c in changes] == [1, 2, None, None]
    assert changes[1]['where'] == '2페이지 · 1번째 문단'
    repeated = [{'where': '본문 문단 2', 'new': '반복', 'old': ''}]
    paragraphs = [{'text': '반복', 'keys': [('본문 문단 1', '반복')]}, {'text': '반복', 'keys': [('본문 문단 2', '반복')]}]
    render.locate_pages(repeated, ['반복', '반복'], paragraphs)
    assert repeated[0]['page'] == 2


def test_preview_publish_and_api_security(pipeline, tmp_path, fake_renderer):
    original = docx_file(tmp_path / 'old.docx', body='Old')
    revised = docx_file(tmp_path / 'new.docx', body='New')
    job = register(pipeline, revised, original=original)
    folder = pipeline.store.job_dir(job['id'])
    before = {p.name: p.read_bytes() for p in (folder / 'inputs').iterdir()}
    pipeline.prepare_preview(job['id'])
    state = pipeline.store.read_status(job['id'])
    assert state['status'] == 'pending' and state['preview']['status'] == 'ready'
    assert read_json(folder / 'review/changes.json')[0]['page'] == 1
    assert (folder / 'review/redline.pdf').is_file()
    assert before == {p.name: p.read_bytes() for p in (folder / 'inputs').iterdir()}
    with TestClient(create_app(pipeline.store.root, pipeline=pipeline), base_url='http://127.0.0.1', backend_options={'loop_factory': client_loop}) as client:
        url = f"/api/jobs/{job['id']}/files/preview/"
        response = client.get(url + 'redline-001.png')
        assert response.status_code == 200 and response.headers['content-type'] == 'image/png'
        assert "img-src 'self'" in response.headers['content-security-policy']
        for name in ['%2e%2e/status.json', '%2e%2e%5cstatus.json', 'a/b.png', 'redline.pdf', 'status.json']:
            assert client.get(url + name).status_code == 404
        image = folder / 'review/preview/redline-001.png'
        image.unlink(); image.symlink_to(original)
        assert client.get(url + image.name).status_code == 404


def test_preview_failure_unavailable_and_no_job_resurrection(pipeline, tmp_path, monkeypatch):
    old, new = docx_file(tmp_path / 'old.docx'), docx_file(tmp_path / 'new.docx', body='new')
    job = register(pipeline, new, original=old)
    monkeypatch.setattr(render, 'find_soffice', lambda _: None)
    pipeline.prepare_preview(job['id'])
    assert pipeline.store.read_status(job['id'])['preview']['status'] == 'unavailable'
    pipeline.store.update_status(job['id'], preview={'status': 'pending'})
    monkeypatch.setattr(render, 'find_soffice', lambda _: Path('/fake'))
    def fail(*args): raise RuntimeError('PRIVATE_BODY')
    monkeypatch.setattr(render, 'convert', fail)
    pipeline.prepare_preview(job['id'])
    state = pipeline.store.read_status(job['id'])
    assert state['preview']['status'] == 'failed' and state['status'] == 'pending'
    assert 'PRIVATE_BODY' not in json.dumps(state)
    pipeline.store.update_status(job['id'], preview={'status': 'pending'})
    def remove(source, destination, *args):
        pipeline.delete(job['id'])
        return tiny_pdf(destination / (source.stem + '.pdf'))
    monkeypatch.setattr(render, 'convert', remove)
    pipeline.prepare_preview(job['id'])
    assert not pipeline.store.job_dir(job['id']).exists()
    assert not list(pipeline.store.path('logs').glob('.render-*'))


def test_preview_does_not_overwrite_translation(pipeline, tmp_path, fake_renderer, monkeypatch):
    job = register(pipeline, docx_file(tmp_path / 'new.docx', body='New'), original=docx_file(tmp_path / 'old.docx', body='Old'))
    entered, release = threading.Event(), threading.Event()
    def factory(lang):
        entered.set(); assert release.wait(10); return FakeAgent(lang)
    pipeline.agent_factory = factory
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(pipeline.start_translation, job['id'])
        try:
            assert entered.wait(10)
            pipeline.prepare_preview(job['id'])
            assert pipeline.store.read_status(job['id'])['status'] == 'translating'
        finally: release.set()
        assert future.result()['status'] == 'translated'
    state = pipeline.store.read_status(job['id'])
    assert state['preview']['status'] == 'ready' and state['progress']['phase'] == 'done'


def test_xlsx_real_addresses_grid_styles_deletions_and_headers(tmp_path):
    old, new = tmp_path / 'old.xlsx', tmp_path / 'new.xlsx'
    wb = Workbook(); ws = wb.active; ws.title = '단가'
    for row in [('품목', '가격'), ('유지', 10), ('수정', 20), ('삭제', 30), ('끝', 40)]: ws.append(row)
    ws.oddHeader.center.text = '기존 머리'; wb.save(old)
    ws.insert_rows(3); ws['A3'] = '새 행'; ws['B3'] = 5; ws['B4'] = 21; ws.delete_rows(5)
    ws['A7'] = '=1+1'; ws.merge_cells('A8:B8'); ws['A8'] = '병합'
    ws['A3'].font = Font(bold=True, italic=True, color='FF123456')
    ws['A3'].fill = PatternFill('solid', fgColor='FFFFFF00')
    ws.column_dimensions['B'].width = 25; ws.row_dimensions[3].height = 30
    ws.oddHeader.center.text = '새 머리'; wb.create_sheet('추가'); wb.save(new)
    reports = compare_sheets(old, new); diff = grid.changes(old, new, reports)
    changed = next(c for c in diff if c.get('cell') == 'B4' and c['op'] == 'modified')
    assert changed['old'] == '20' and changed['new'] == '21' and changed['where'] == "'단가' 시트 · B4"
    assert any(c['where'] == "'단가' 시트 · 머리글(가운데)" for c in diff)
    assert any(c['where'] == "'추가' 시트 전체" for c in diff)
    assert any(c.get('source') == 'original' and c['where'].endswith('(원본)') for c in diff)
    sheet = grid.build(old, new, reports, diff)[0]
    assert sheet['changes']['B4']['old'] == '20'
    cells = {cell['addr']: cell for row in sheet['rows'] for cell in row['cells']}
    assert cells['A3']['bold'] and cells['A3']['italic'] and cells['A3']['color'] == '#123456'
    assert cells['A7']['value'] == '=1+1' and cells['A8']['span'] == {'rows': 1, 'cols': 2}
    assert 'B8' not in cells and sheet['cols'][1]['width'] > 170
    assert sheet['rows'][2]['height'] == 30
    assert any(row['index'] == 4 and row['after'] == 4 for row in sheet['removed_rows'])


def test_grid_limits_keep_distant_changes(tmp_path):
    old, new = tmp_path / 'old.xlsx', tmp_path / 'new.xlsx'
    wb = Workbook(); wb.active['A1'] = '처음'; wb.active['DW2100'] = '이전'; wb.save(old)
    wb.active['DW2100'] = '새 값'; wb.save(new)
    reports = compare_sheets(old, new); diff = grid.changes(old, new, reports)
    sheet = grid.build(old, new, reports, diff)[0]
    assert len(sheet['rows']) == 2000 and len(sheet['cols']) == 100 and sheet['message']
    assert 2100 in [row['index'] for row in sheet['rows']]
    assert 'DW' in [col['letter'] for col in sheet['cols']]
    assert sheet['changes']['DW2100']['new'] == '새 값'


def test_pptx_shape_labels_and_group_overlay(tmp_path):
    from app.engine import extract_with_locations
    from app.diff.pptx import build
    old = pptx_file(tmp_path / 'old.pptx'); new = tmp_path / 'new.pptx'
    prs = Presentation(old); slide = prs.slides[0]
    slide.shapes.add_table(2, 2, Inches(1), Inches(3), Inches(4), Inches(1)).table.cell(0, 0).text = '표 내용'
    group = slide.shapes.add_group_shape()
    child = group.shapes.add_textbox(Inches(1), Inches(1), Inches(2), Inches(1)); child.text = 'old-group'
    prs.save(old); child.text = 'new-group'; prs.save(new)
    texts, locations = extract_with_locations(old)
    assert locations[texts.index('기존 제목')] == '슬라이드 1 · 제목'
    assert '발표자 노트' in locations[texts.index('발표자 노트')]
    assert '표 1행 1열' in locations[texts.index('표 내용')]
    report = tmp_path / 'slides.json'; build(old, new, report)
    boxes = overlays(old, new, read_json(report))
    assert {box['side'] for box in boxes} == {'original', 'revised'}
    assert boxes[0]['x'] == group.left / prs.slide_width
    assert boxes[0]['width'] == group.width / prs.slide_width


def test_batches_callback_cache_validation_and_numeric_progress():
    inner = FakeAgent('test'); events = []
    agent = ReuseAgent({'reuse': '기존'}, inner, progress_batch=2, callback=lambda phase, stats: events.append((phase, stats)))
    output = agent.send_segments(['reuse', 'one', 'two', 'three', 'one', '123'], 3000)
    assert inner.calls == [['one', 'two'], ['three']] and output[1] == output[4]
    assert agent.stats == {'segments': 6, 'reused': 1, 'translated': 3}
    assert [s['count'] for phase, s in events if phase == 'batch'] == [2, 1]
    assert all(not isinstance(v, str) for _, stats in events for v in stats.values())
    class Broken(FakeAgent):
        def send_segments(self, segments, chunk_size): return []
    with pytest.raises(TranslationError): ReuseAgent({}, Broken('test'), progress_batch=1).send_segments(['one'], 3)


def test_progress_eta_throttled_snapshots_and_log_bound():
    clock = [0.0]; saves = []
    plans = {'zh-CN': {'reused': 1, 'translated': 4}, 'zh-TW': {'reused': 0, 'translated': 4}}
    progress = Progress(plans, lambda value: saves.append((clock[0], json.loads(json.dumps(value)))), clock=lambda: clock[0])
    progress.record('zh-CN', 'extract'); progress.record('zh-CN', 'reuse', {'reused': 1})
    assert len(saves) == 1 and progress.value['eta_sec'] is None
    progress.record('zh-CN', 'batch', {'count': 2, 'batch': 1, 'batches': 2, 'elapsed': 4, 'translated': 2})
    assert progress.value['eta_sec'] == 12
    clock[0] = 1.1; progress.record('zh-CN', 'write')
    assert len(saves) == 2 and saves[-1][1]['langs']['zh-CN']['done'] == 3
    for _ in range(100): progress.record('zh-CN', 'write')
    assert len(progress.value['log']) == 50 and len(saves) == 2


@pytest.mark.skipif(not os.environ.get('DOC_TRANSLATE_SOFFICE'), reason='DOC_TRANSLATE_SOFFICE를 지정한 경우만 실제 LibreOffice 실행')
@pytest.mark.parametrize('ext,maker', [('docx', docx_file), ('pptx', pptx_file)])
def test_libreoffice_integration(pipeline, tmp_path, ext, maker):
    old = maker(tmp_path / f'old.{ext}', body='Old paragraph')
    new = maker(tmp_path / f'new.{ext}', body='New paragraph')
    job = register(pipeline, new, original=old)
    pipeline.prepare_preview(job['id'])
    folder = pipeline.store.job_dir(job['id'])
    state = pipeline.store.read_status(job['id'])
    assert state['preview']['status'] == 'ready', state['preview']
    assert state['status'] == 'pending'
    for page in state['preview']['pages']:
        assert (folder / 'review/preview' / page['name']).read_bytes().startswith(b'\x89PNG')
    if ext == 'docx':
        assert read_json(folder / 'review/changes.json')[0]['page'] == 1
        assert (folder / 'review/redline.pdf').exists()
    else:
        assert {page['side'] for page in state['preview']['pages']} == {'original', 'revised'}
        assert read_json(folder / 'review/preview/overlays.json')
    assert not list(pipeline.store.path('logs/.lo-profile').iterdir())


def test_upload_schedules_preview_after_pending_response(pipeline, tmp_path, fake_renderer):
    old, new = docx_file(tmp_path / 'old.docx', body='Old'), docx_file(tmp_path / 'new.docx', body='New')
    with TestClient(create_app(pipeline.store.root, pipeline=pipeline), base_url='http://127.0.0.1', backend_options={'loop_factory': client_loop}) as client:
        response = client.post('/api/jobs', files={'original': ('old.docx', old.read_bytes()), 'revised': ('new.docx', new.read_bytes())})
        assert response.status_code == 201
        pending = response.json()
        assert pending['preview']['status'] == 'pending'
        ready = client.get(f"/api/jobs/{pending['id']}").json()
        assert ready['preview']['status'] == 'ready' and ready['status'] == 'pending'
        assert not ready['outputs'] and not ready.get('progress')


def test_grid_api_formula_cached_value_and_read_only_inputs(pipeline, tmp_path):
    from zipfile import ZipFile
    from io import BytesIO
    old, new = tmp_path / 'old.xlsx', tmp_path / 'new.xlsx'
    wb = Workbook(); wb.active['A1'] = 'Old'; wb.active['B1'] = '=1+1'; wb.save(old)
    wb.active['A1'] = 'New'; wb.save(new)
    content = BytesIO()
    with ZipFile(new) as source, ZipFile(content, 'w') as dest:
        for info in source.infolist():
            data = source.read(info.filename)
            if info.filename == 'xl/worksheets/sheet1.xml':
                data = data.replace(b'<f>1+1</f><v></v>', b'<f>1+1</f><v>2</v>')
            dest.writestr(info, data)
    new.write_bytes(content.getvalue())
    job = register(pipeline, new, original=old)
    before = new.read_bytes()
    with TestClient(create_app(pipeline.store.root, pipeline=pipeline), base_url='http://127.0.0.1', backend_options={'loop_factory': client_loop}) as client:
        url = f"/api/jobs/{job['id']}"
        sheet = client.get(url + '/grid').json()[0]
        assert sheet['changes']['A1']['new'] == 'New'
        assert sheet['rows'][0]['cells'][1]['value'] == '2'
        assert client.get(url + '/grid?row=0').status_code == 422
        assert client.get(url + '/grid', headers={'host': 'evil.example'}).status_code == 400
        assert client.post(url + '/translate', headers={'origin': 'https://evil.example'}).status_code == 403
    assert new.read_bytes() == before
    assert (pipeline.store.job_dir(job['id']) / 'inputs/revised.xlsx').read_bytes() == before


def test_render_lock_serializes_calls(tmp_path):
    entered, release, second = threading.Event(), threading.Event(), threading.Event()
    def first():
        with render.render_lock(tmp_path):
            entered.set(); assert release.wait(5)
    def other():
        with render.render_lock(tmp_path): second.set()
    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(first)
        assert entered.wait(5)
        b = pool.submit(other)
        try: assert not second.wait(.05)
        finally: release.set()
        a.result(); b.result()
    assert second.is_set()


def test_grid_merged_cell_retains_hidden_change_address(tmp_path):
    old, new = tmp_path / 'old.xlsx', tmp_path / 'new.xlsx'
    wb = Workbook(); ws = wb.active
    ws.append(['anchor', 'hidden']); wb.save(old)
    ws.merge_cells('A1:B1'); wb.save(new)
    reports = compare_sheets(old, new)
    diff = grid.changes(old, new, reports)
    sheet = grid.build(old, new, reports, diff)[0]
    assert sheet['rows'][0]['cells'][0]['change_addrs'] == ['B1']
    assert sheet['changes']['B1']['old'] == 'hidden'
