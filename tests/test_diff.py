import json
from zipfile import ZipFile

from openpyxl import load_workbook

from app.diff import docx, xlsx, pptx
from app.diff.segments import compare
from tests.documents import docx_file, xlsx_file, pptx_file


def test_segment_diff_order_and_locations():
    changes = compare(['유지', '수정 전', '삭제'], ['추가', '유지', '수정 후'])
    assert changes[0] == {'op':'added', 'old':'', 'new':'추가', 'where':'세그먼트 1'}
    assert any(c['op']=='modified' and c['old']=='수정 전' and c['new']=='수정 후' for c in changes)
    assert any(c['op']=='removed' and c['old']=='삭제' for c in changes)
    assert compare(['그대로'], ['그대로']) == []


def test_docx_real_redline(tmp_path):
    old = docx_file(tmp_path/'old.docx', body='Old sentence.')
    new = docx_file(tmp_path/'new.docx', body='New sentence added.')
    target = tmp_path/'redline.docx'
    docx.build(old, new, target, cache_dir=tmp_path.parent/'docxodus-cache')
    with ZipFile(target) as z:
        content = z.read('word/document.xml')
        assert b'<w:ins' in content and b'<w:del' in content
        assert b'doc-translate' in content


def test_xlsx_daff_rows_formulas_sheets_and_escaping(tmp_path):
    old = xlsx_file(tmp_path/'old.xlsx')
    new = tmp_path/'new.xlsx'
    wb = load_workbook(old)
    ws = wb.active
    ws.insert_rows(3)
    ws['A3'] = '끼운 행'
    ws['B3'] = '<script>alert(1)</script>'
    ws['A4'] = '=SUM(2,3)'
    wb.create_sheet('새 시트')['A1'] = '새 값'
    wb.save(new)
    target = tmp_path/'sheets.html'
    xlsx.build(old, new, target)
    content = target.read_text()
    assert '+++' in content and '끼운 행' in content
    assert 'SUM(1,2)' in content and 'SUM(2,3)' in content
    assert '새 시트' in content and '시트 추가' in content
    assert '<script>' not in content and '&lt;script&gt;' in content
    xlsx.build(new, old, target)
    assert '시트 삭제' in target.read_text()


def test_pptx_slide_and_notes_changes(tmp_path):
    old = pptx_file(tmp_path/'old.pptx')
    new = pptx_file(tmp_path/'new.pptx', body='바뀐 제목')
    target = tmp_path/'slides.json'
    pptx.build(old, new, target)
    changes = json.loads(target.read_text())
    assert changes and changes[0]['slide'] == 1
    assert changes[0]['shape'] and not changes[0]['notes']
    assert changes[0]['old'] == '기존 제목' and changes[0]['new'] == '바뀐 제목'
    pptx.build(None, new, target)
    assert any(c['notes'] and c['new']=='발표자 노트' for c in json.loads(target.read_text()))
