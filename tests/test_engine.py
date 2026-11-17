from io import BytesIO
from zipfile import ZipFile

from docx import Document
from lxml import etree
from openpyxl import load_workbook
from pptx import Presentation
import pytest

from app.engine import extract, translate
from app.reuse_agent import FakeAgent, ReuseAgent
from app.xlsx_headers import transform
from tests.documents import docx_file, xlsx_file, pptx_file, image_file, rewrite_zip


@pytest.mark.parametrize('ext,maker', [('docx',docx_file), ('xlsx',xlsx_file), ('pptx',pptx_file)])
def test_library_translation_and_preservation(tmp_path, ext, maker):
    source = maker(tmp_path/f'input.{ext}', image=image_file(tmp_path))
    original = source.read_bytes()
    agent = ReuseAgent({}, FakeAgent('zh-CN'))
    result = translate(source, agent)
    assert source.read_bytes() == original
    with ZipFile(BytesIO(original)) as before, ZipFile(BytesIO(result)) as after:
        for name in before.namelist():
            if '/media/' in name:
                assert before.read(name) == after.read(name)
    texts = extract(source)
    if ext == 'docx':
        assert {'기존 본문', '유지 문단', '표 내용', '머리글', '바닥글'} <= set(texts)
        assert '번역 금지 메모' not in texts
        doc = Document(BytesIO(result))
        assert doc.paragraphs[0].text == '[zh-CN] 기존 본문'
        assert next(iter(doc.comments)).text == '번역 금지 메모'
        assert doc.sections[0].header.paragraphs[0].text == '[zh-CN] 머리글'
    elif ext == 'xlsx':
        assert {'기존 셀','유지 셀','회사명','설계서','바닥글'} <= set(texts)
        assert not {'=SUM(1,2)', '123', '원문 시트명', '번역 금지 메모'} & set(texts)
        ws = load_workbook(BytesIO(result), data_only=False).active
        assert ws.title == '원문 시트명'
        assert ws['A3'].value == '=SUM(1,2)' and ws['B3'].value == 123
        assert ws['A2'].comment.text == '번역 금지 메모'
        assert ws['B2'].value == '[zh-CN] 기존 셀'
    else:
        assert {'기존 제목','유지 본문','발표자 노트'} <= set(texts)
        assert any('Master title style' in s for s in texts)
        prs = Presentation(BytesIO(result))
        assert prs.slides[0].shapes.title.text == '[zh-CN] 기존 제목'
        assert prs.slides[0].notes_slide.notes_text_frame.text == '[zh-CN] 발표자 노트'
    # One call from docutranslate (xlsx header/footer adds its own call).
    assert len(agent.inner.calls) == (2 if ext == 'xlsx' else 1)


def test_docx_notes_textbox_and_partial_style_limit(tmp_path):
    path = docx_file(tmp_path/'rich.docx', rich=True, extra_parts=True)
    texts = extract(path)
    assert {'각주 내용','미주 내용','텍스트 상자','밑줄 텍스트'} <= set(texts)
    result = translate(path, ReuseAgent({}, FakeAgent('zh-TW')))
    doc = Document(BytesIO(result))
    assert doc.paragraphs[0].text == '[zh-TW] 굵은 기존 본문'
    assert doc.paragraphs[0].runs[0].bold
    assert not any(r.italic for r in doc.paragraphs[0].runs if r.text)
    assert any(r.underline for p in doc.paragraphs for r in p.runs if '밑줄' in r.text)


def test_xlsx_headers_only_patch_sheet_xml_and_keep_controls(tmp_path):
    path = xlsx_file(tmp_path/'input.xlsx')
    agent = ReuseAgent({}, FakeAgent('zh-TW'))
    result = transform(path.read_bytes(), agent)
    with ZipFile(path) as src, ZipFile(BytesIO(result)) as dst:
        for name in src.namelist():
            if name != 'xl/worksheets/sheet1.xml':
                assert src.read(name) == dst.read(name)
        sheet = etree.fromstring(dst.read('xl/worksheets/sheet1.xml'))
        ns = {'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
        header = sheet.find('s:headerFooter/s:oddHeader', ns).text
        assert '&L[zh-TW] 회사명' in header
        assert '&C&"Arial,Bold"&12[zh-TW] 설계서 &P / &N' in header
        assert all('[zh-TW]' in s.text for s in sheet.find('s:headerFooter', ns))
        assert '&D' in sheet.find('s:headerFooter/s:oddFooter', ns).text
    assert agent.inner.calls[0].count('회사명') == 1


def test_xlsx_shared_strings_deduplicated(tmp_path):
    path = xlsx_file(tmp_path/'shared.xlsx')
    with ZipFile(path) as src:
        xml = etree.fromstring(src.read('xl/worksheets/sheet1.xml'))
        types = etree.fromstring(src.read('[Content_Types].xml'))
        rels = etree.fromstring(src.read('xl/_rels/workbook.xml.rels'))
    ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    for c in xml.findall(f'.//{{{ns}}}c')[:2]:
        for child in list(c): c.remove(child)
        c.set('t','s')
        etree.SubElement(c, f'{{{ns}}}v').text = '0'
    etree.SubElement(types,'{http://schemas.openxmlformats.org/package/2006/content-types}Override',
        PartName='/xl/sharedStrings.xml', ContentType='application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml')
    etree.SubElement(rels,'{http://schemas.openxmlformats.org/package/2006/relationships}Relationship',
        Id='rIdShared', Type='http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings', Target='sharedStrings.xml')
    rewrite_zip(path, {'xl/worksheets/sheet1.xml':etree.tostring(xml), '[Content_Types].xml':etree.tostring(types),
        'xl/_rels/workbook.xml.rels':etree.tostring(rels),
        'xl/sharedStrings.xml':f'<sst xmlns="{ns}" count="2" uniqueCount="1"><si><t>공유 텍스트</t></si></sst>'.encode()})
    assert extract(path).count('공유 텍스트') == 1
    output = translate(path, ReuseAgent({}, FakeAgent('zh-CN')))
    ws = load_workbook(BytesIO(output)).active
    assert ws['A1'].value == ws['B1'].value == '[zh-CN] 공유 텍스트'


def test_docx_inline_style_boundaries_and_note_output(tmp_path):
    from docx.shared import RGBColor
    from docx.enum.text import WD_COLOR_INDEX
    path=docx_file(tmp_path/'notes.docx',extra_parts=True)
    doc=Document(path)
    paragraph=doc.add_paragraph()
    first=paragraph.add_run('빨간색 ')
    first.font.color.rgb=RGBColor(255,0,0)
    second=paragraph.add_run('파란색')
    second.font.color.rgb=RGBColor(0,0,255)
    paragraph=doc.add_paragraph()
    paragraph.add_run('일반')
    paragraph.add_run('밑줄').underline=True
    paragraph.add_run('형광펜').font.highlight_color=WD_COLOR_INDEX.YELLOW
    paragraph.add_run('취소선').font.strike=True
    paragraph.add_run('위첨자').font.superscript=True
    doc.save(path)
    texts=extract(path)
    assert '빨간색 파란색' in texts
    assert {'일반','밑줄','형광펜','취소선','위첨자'} <= set(texts)
    translated=translate(path,ReuseAgent({},FakeAgent('zh-CN')))
    doc=Document(BytesIO(translated))
    merged=next(p for p in doc.paragraphs if '빨간색' in p.text)
    assert all(r.font.color.rgb==RGBColor(255,0,0) for r in merged.runs if r.text)
    runs={r.text:r for p in doc.paragraphs for r in p.runs}
    assert runs['[zh-CN] 밑줄'].underline
    assert runs['[zh-CN] 형광펜'].font.highlight_color==WD_COLOR_INDEX.YELLOW
    assert runs['[zh-CN] 취소선'].font.strike
    assert runs['[zh-CN] 위첨자'].font.superscript
    with ZipFile(BytesIO(translated)) as archive:
        for kind,label in [('footnotes','각주 내용'),('endnotes','미주 내용')]:
            assert f'[zh-CN] {label}'.encode() in archive.read(f'word/{kind}.xml')


def test_xlsx_extraction_is_stable_across_python_hash_seeds(tmp_path):
    import os
    import subprocess
    import sys
    from openpyxl import Workbook
    path=tmp_path/'hash.xlsx'
    wb=Workbook()
    for i in range(80):
        wb.active.append([f'문장 {i:03d}'])
    wb.save(path)
    code='import json,sys; from pathlib import Path; from app.engine import extract; print(json.dumps(extract(Path(sys.argv[1]))))'
    results=[subprocess.check_output([sys.executable,'-c',code,str(path)],
             env={**os.environ,'PYTHONHASHSEED':str(seed)}) for seed in (1,2)]
    assert results[0]==results[1]
