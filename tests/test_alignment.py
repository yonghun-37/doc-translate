from pathlib import Path

from docx import Document
from openpyxl import Workbook, load_workbook
from pptx import Presentation
import pytest

from app import alignment, engine
from app.reuse_agent import FakeAgent, ReuseAgent, needs_translation
from tests.documents import docx_file, pptx_file, xlsx_file


@pytest.mark.parametrize('ext,maker', [('docx', docx_file), ('pptx', pptx_file), ('xlsx', xlsx_file)])
def test_generated_translation_matches_original(tmp_path, ext, maker):
    original = maker(tmp_path / f'original.{ext}')
    base = tmp_path / f'base.{ext}'
    base.write_bytes(engine.translate(original, ReuseAgent({}, FakeAgent('zh-CN'))))
    before, after = engine.extract_with_locations(original), engine.extract_with_locations(base)
    if ext != 'xlsx':
        assert before[1] == after[1] and len(before[0]) == len(after[0])
    memory, result = alignment.build(original, base, 'zh-CN')
    eligible = [text for text in before[0] if needs_translation(text)]
    assert all(memory[text] == f'[zh-CN] {text}' for text in eligible)
    assert result['total'] == len(before[0])
    assert result['matched'] == len(eligible)


@pytest.mark.parametrize('operation', ['add', 'remove'])
@pytest.mark.parametrize('ext', ['docx', 'pptx'])
def test_edited_paragraph_group_is_unmatched_while_other_groups_survive(tmp_path, ext, operation):
    original, base = tmp_path / f'original.{ext}', tmp_path / f'base.{ext}'
    if ext == 'docx':
        doc = Document()
        doc.add_paragraph('유지 본문')
        cell = doc.add_table(rows=1, cols=1).cell(0, 0)
        cell.text = '변경 그룹 첫 문장'
        cell.add_paragraph('변경 그룹 둘째 문장')
        doc.save(original)
    else:
        doc = Presentation()
        slide = doc.slides.add_slide(doc.slide_layouts[1])
        slide.shapes.title.text = '유지 본문'
        frame = slide.placeholders[1].text_frame
        frame.text = '변경 그룹 첫 문장'
        frame.add_paragraph().text = '변경 그룹 둘째 문장'
        doc.save(original)
    base.write_bytes(engine.translate(original, ReuseAgent({}, FakeAgent('zh-CN'))))
    if ext == 'docx':
        doc = Document(base)
        group = doc.tables[0].cell(0, 0)
    else:
        doc = Presentation(base)
        group = doc.slides[0].placeholders[1].text_frame
    if operation == 'add':
        group.add_paragraph().text = '人工添加'
    else:
        element = group.paragraphs[-1]._p
        element.getparent().remove(element)
    doc.save(base)
    memory, result = alignment.build(original, base, 'zh-CN')
    assert memory['유지 본문'] == '[zh-CN] 유지 본문'
    assert '변경 그룹 첫 문장' not in memory and '변경 그룹 둘째 문장' not in memory
    assert {s['text'] for s in result['unmatched_samples']} >= {'변경 그룹 첫 문장', '변경 그룹 둘째 문장'}


def test_sequence_alignment_skips_missing_and_extra_location_keys():
    before = (['가', '나', '다'], ['A', 'B', 'C'])
    after = (['新增', '甲', '丙'], ['extra', 'A', 'C'])
    assert alignment.location_pairs(before, after) == [('가', '甲'), ('다', '丙')]


def test_xlsx_matches_addresses_sheet_names_then_order_and_excludes_formulas(tmp_path):
    original, base = tmp_path / 'original.xlsx', tmp_path / 'base.xlsx'
    wb = Workbook()
    ws = wb.active
    ws.title = '원본 시트'
    for addr, value in [('A1', '가나다'), ('A2', '라마바'), ('B1', '=SUM(1,2)'), ('B2', '번역 비어 있음'), ('C1', '변경 없음')]:
        ws[addr] = value
    ws.oddHeader.left.text = '머리글'
    ws.oddFooter.right.text = '바닥글'
    wb.create_sheet('같은 이름')['A1'] = '두번째'
    wb.save(original)
    translated = Workbook()
    ws = translated.active
    ws.title = '中文工作表'
    # Deliberately reverse text sorting and cell assignment order.
    for addr, value in [('A2', '甲'), ('A1', '乙'), ('B1', '数式'), ('B2', ''), ('C1', '변경 없음')]:
        ws[addr] = value
    ws.oddHeader.left.text = '页眉'
    ws.oddFooter.right.text = '页脚'
    translated.create_sheet('같은 이름')['A1'] = '第二'
    translated.save(base)
    original_bytes, base_bytes = original.read_bytes(), base.read_bytes()
    memory, result = alignment.build(original, base, 'zh-CN')
    assert memory == {'가나다': '乙', '라마바': '甲', '머리글': '页眉', '바닥글': '页脚', '두번째': '第二'}
    assert not any(text.startswith('=') for text in memory)
    assert any(s['where'] == '원본 시트 · B2' for s in result['unmatched_samples'])
    assert original.read_bytes() == original_bytes and base.read_bytes() == base_bytes


def test_xlsx_exact_sheet_names_win_after_reorder(tmp_path):
    original, base = tmp_path / 'original.xlsx', tmp_path / 'base.xlsx'
    wb = Workbook(); wb.active.title = '첫째'; wb.active['A1'] = '첫 값'
    wb.create_sheet('둘째')['A1'] = '둘째 값'; wb.save(original)
    target = Workbook(); target.active.title = '둘째'; target.active['A1'] = '第二'
    target.create_sheet('첫째')['A1'] = '第一'; target.save(base)
    memory, _ = alignment.build(original, base, 'zh-CN')
    assert memory == {'첫 값': '第一', '둘째 값': '第二'}


def test_conflicting_translations_majority_then_first_and_empty_identity_excluded():
    assert alignment.memory_from_pairs([
        ('동률', '先'), ('동률', '后'), ('다수', '一'), ('다수', '二'), ('다수', '二'),
        ('그대로', '그대로'), ('빈 번역', '  '),
    ]) == {'동률': '先', '다수': '二'}


def test_xlsx_conflicting_cell_translations_vote_by_occurrences(tmp_path):
    paths = [tmp_path / 'original.xlsx', tmp_path / 'base.xlsx']
    for path, values in zip(paths, [['중복'] * 3, ['첫째', '다수', '다수']]):
        wb = Workbook()
        for value in values: wb.active.append([value])
        wb.save(path)
    memory, _ = alignment.build(*paths, 'zh-CN')
    assert memory['중복'] == '다수'


def test_unmatched_samples_capped_and_plan_excludes_numbers_and_duplicates(tmp_path):
    source, base = tmp_path / 'source.docx', tmp_path / 'base.docx'
    doc = Document()
    for i in range(30): doc.add_paragraph(f'원문 {i}')
    doc.save(source); doc.save(base)
    memory, result = alignment.build(source, base, 'zh-CN')
    assert not memory and result['total'] == 30 and result['matched'] == 0
    assert len(result['unmatched_samples']) == 20
    assert alignment.translation_plan(['유지', '변경', '변경', '123', '10 kg'], {'유지': '旧'}) == {
        'segments': 5, 'reused': 1, 'translated': 1}
