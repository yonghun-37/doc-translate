from html import escape
from pathlib import Path

import daff
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

from app.storage import atomic_write, write_json


def _sheets(path):
    if path is None:
        return {}
    wb = load_workbook(path, data_only=False, read_only=True)
    try:
        return {ws.title: [[str(cell) if cell is not None else '' for cell in row]
                           for row in ws.iter_rows(values_only=True)] for ws in wb.worksheets}
    finally:
        wb.close()


def build(old: Path | None, new: Path, destination: Path):
    before, after = _sheets(old), _sheets(new)
    sections = []
    for name in dict.fromkeys([*before, *after]):
        a, b = before.get(name, []), after.get(name, [])
        width = max([len(row) for row in a + b], default=1)
        header = [get_column_letter(i+1) for i in range(width)]
        def table(rows):
            return daff.PythonTableView([header] + [row + ['']*(width-len(row)) for row in rows])
        alignment = daff.Coopy.compareTables(table(a), table(b)).align()
        diff = daff.PythonTableView([])
        daff.TableDiff(alignment, daff.CompareFlags()).hilite(diff)
        renderer = daff.DiffRender()
        renderer.usePrettyArrows(False)
        renderer.render(diff)
        label = '시트 추가' if name not in before else '시트 삭제' if name not in after else '시트 비교'
        sections.append(f'<section><h2>{escape(name)} — {label}</h2>{renderer.html()}</section>')
    css = daff.DiffRender().sampleCss()
    html = ('<!doctype html><html lang="ko"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>시트 비교</title><style>{css}body{{font-family:system-ui;margin:20px}}'
            'section{overflow:auto}td{white-space:pre-wrap}</style><body>'
            '<p>+++ 추가 행 · --- 삭제 행 · -&gt; 변경된 셀</p>' + ''.join(sections) + '</body></html>')
    atomic_write(destination, html.encode())


def compare_sheets(old: Path | None, new: Path) -> list[dict]:
    before, after = _sheets(old), _sheets(new)
    result = []
    for name in dict.fromkeys([*before, *after]):
        a, b = before.get(name, []), after.get(name, [])
        width = max([len(row) for row in a + b], default=1)
        header = [get_column_letter(i + 1) for i in range(width)]
        def table(rows):
            return daff.PythonTableView([header] + [row + [''] * (width - len(row)) for row in rows])
        alignment = daff.Coopy.compareTables(table(a), table(b)).align()
        diff = daff.PythonTableView([])
        daff.TableDiff(alignment, daff.CompareFlags()).hilite(diff)
        rows = []
        for y in range(diff.get_height()):
            cells = [str(diff.getCell(x, y)) if diff.getCell(x, y) is not None else '' for x in range(diff.get_width())]
            if cells and cells[0] == '@@':
                header = cells[1:]
            elif cells:
                rows.append({'marker': cells[0], 'cells': cells[1:]})
        status = 'added' if name not in before else 'removed' if name not in after else 'same' if a == b else 'changed'
        result.append({'sheet': name, 'status': status, 'header': header, 'rows': rows,
                       'row_pairs': [[unit.l, unit.r] for unit in alignment.toOrder().getList()
                                     if unit.l != 0 and unit.r != 0]})
    return result


def build_json(old: Path | None, new: Path, destination: Path):
    write_json(destination, compare_sheets(old, new))
