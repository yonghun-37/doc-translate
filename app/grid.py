"""Read-only spreadsheet view, using daff's row correspondence for real addresses."""
from contextlib import ExitStack
from datetime import date, datetime
import re
from zipfile import ZipFile

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter, range_boundaries, coordinate_to_tuple
from app import xlsx_headers
from app.xlsx_headers import _xml, _NS


def value(cell):
    val = cell.value
    if val is None:
        return ''
    if isinstance(val, (date, datetime)):
        return val.isoformat(sep=' ') if isinstance(val, datetime) else val.isoformat()
    if isinstance(val, bool):
        return 'TRUE' if val else 'FALSE'
    if isinstance(val, float):
        return str(int(val)) if val.is_integer() else str(val)
    return str(val)


def changes(original, revised, sheets):
    result = []
    with ExitStack() as stack:
        before = load_workbook(original, read_only=True) if original else None
        after = load_workbook(revised, read_only=True)
        if before:
            stack.callback(before.close)
        stack.callback(after.close)
        for report in sheets:
            name, status = report['sheet'], report['status']
            if status in {'added', 'removed'}:
                result.append({'op': status, 'sheet': name, 'where': f"'{name}' 시트 전체", 'old': '', 'new': ''})
                continue
            old_rows = list(before[name].iter_rows()) if before else []
            new_rows = list(after[name].iter_rows())
            for old_index, new_index in report['row_pairs']:
                a = old_rows[old_index - 1] if old_index > 0 else ()
                b = new_rows[new_index - 1] if new_index > 0 else ()
                for col in range(max(len(a), len(b))):
                    old = value(a[col]) if col < len(a) else ''
                    new = value(b[col]) if col < len(b) else ''
                    if old == new:
                        continue
                    op = 'removed' if new_index < 0 or not new else 'added' if old_index < 0 or not old else 'modified'
                    addr = f'{get_column_letter(col + 1)}{old_index if new_index < 0 else new_index}'
                    result.append({'op': op, 'sheet': name, 'cell': addr, 'old': old, 'new': new,
                                   'source': 'original' if new_index < 0 else 'revised',
                                   'where': f"'{name}' 시트 · {addr}" + (' (원본)' if new_index < 0 else '')})
    a, b = xlsx_headers.located(original) if original else {}, xlsx_headers.located(revised)
    for key in dict.fromkeys([*a, *b]):
        if a.get(key, '') == b.get(key, ''):
            continue
        name, kind = key
        result.append({'op': 'modified' if key in a and key in b else 'added' if key in b else 'removed',
                       'where': f"'{name}' 시트 · {kind}", 'sheet': name, 'old': a.get(key, ''), 'new': b.get(key, '')})
    return result


def _selection(maximum, important, limit, focus=None):
    selected = set()
    # A requested location has priority, then all changes, then their neighbours.
    priorities = ([focus] if focus else []) + sorted(important)
    for n in priorities:
        if 1 <= n <= maximum and len(selected) < limit:
            selected.add(n)
    for n in priorities:
        for neighbour in (n - 1, n + 1):
            if 1 <= neighbour <= maximum and len(selected) < limit:
                selected.add(neighbour)
    for n in range(1, min(maximum, limit) + 1):
        if len(selected) >= limit:
            break
        selected.add(n)
    return sorted(selected)


def _metadata(path, sheet):
    with ZipFile(path) as src:
        root = _xml(src.read(f'xl/worksheets/{sheet}'))
    ns = f'{{{_NS}}}'
    return ([node.attrib for node in root.findall(f'{ns}cols/{ns}col')],
            {int(n.get('r')): float(n.get('ht')) for n in root.findall(f'{ns}sheetData/{ns}row') if n.get('ht')},
            [n.get('ref') for n in root.findall(f'{ns}mergeCells/{ns}mergeCell')])


def _color(color):
    return '#' + color.rgb[-6:] if color and color.type == 'rgb' and re.fullmatch('[0-9a-fA-F]{8}', color.rgb) else None


def _cell(cell, cached=None):
    result = {'addr': cell.coordinate, 'value': value(cached if cached is not None and cached.value is not None else cell)}
    if cell.font:
        result.update(bold=bool(cell.font.b), italic=bool(cell.font.i))
        if color := _color(cell.font.color):
            result['color'] = color
    if cell.fill and cell.fill.patternType == 'solid' and (color := _color(cell.fill.fgColor)):
        result['fill'] = color
    if cell.alignment and cell.alignment.horizontal in {'left', 'center', 'right'}:
        result['align'] = cell.alignment.horizontal
    return result


def build(original, revised, reports, all_changes, *, sheet=None, row=None, col=None):
    result = []
    with ExitStack() as stack:
        def book(path, data_only=False):
            wb = load_workbook(path, read_only=True, data_only=data_only)
            stack.callback(wb.close)
            return wb
        after, cache = book(revised), book(revised, True)
        before = book(original) if original else None
        for report in reports:
            name, status = report['sheet'], report['status']
            source = before if status == 'removed' else after
            ws = source[name]
            # ReadOnlyWorksheet preserves styles, but not dimensions or merges.
            part = ws._worksheet_path.rsplit('/', 1)[-1]
            widths, heights, merges = _metadata(original if status == 'removed' else revised, part)
            relevant = [c for c in all_changes if c.get('sheet') == name and c.get('cell')]
            target_changes = {c['cell']: {k: c[k] for k in ('op', 'old', 'new')} for c in relevant if c.get('source') != 'original'}
            coords = [coordinate_to_tuple(c['cell']) for c in relevant]
            pairs = report['row_pairs']
            added = {b for a, b in pairs if a < 0 and b > 0}
            important_rows = {r for r, _ in coords} | added
            removed_after, previous = {}, 0
            for a, b in pairs:
                if b > 0:
                    previous = b
                elif a > 0:
                    removed_after[a] = previous
                    important_rows.add(max(1, previous))
            rows = _selection(ws.max_row, important_rows, 2000, row if name == sheet else None)
            cols = _selection(ws.max_column, {c for _, c in coords}, 100, col if name == sheet else None)
            row_set = set(rows)
            merge_at, merge_changes, hidden = {}, {}, set()
            for ref in merges:
                c1, r1, c2, r2 = range_boundaries(ref)
                rr, cc = [r for r in rows if r1 <= r <= r2], [c for c in cols if c1 <= c <= c2]
                if rr and cc and rr[0] == r1 and cc[0] == c1:
                    merge_at[(r1, c1)] = {'rows': len(rr), 'cols': len(cc)}
                    merge_changes[(r1, c1)] = [addr for addr in target_changes
                                               if r1 <= coordinate_to_tuple(addr)[0] <= r2
                                               and c1 <= coordinate_to_tuple(addr)[1] <= c2]
                    hidden.update((r, c) for r in rr for c in cc if (r, c) != (r1, c1))
            grid_rows = []
            cached_rows = iter(cache[name].iter_rows(max_row=max(rows, default=1), max_col=max(cols, default=1))) if status != 'removed' else None
            for ri, cells in enumerate(ws.iter_rows(max_row=max(rows, default=1), max_col=max(cols, default=1)), 1):
                cached = next(cached_rows, ()) if cached_rows else ()
                if ri not in row_set:
                    continue
                data = []
                for ci in cols:
                    if (ri, ci) in hidden:
                        continue
                    cell = cells[ci - 1]
                    entry = _cell(cell, cached[ci - 1] if cached else None) if hasattr(cell, 'coordinate') else {'addr': f'{get_column_letter(ci)}{ri}', 'value': ''}
                    if (ri, ci) in merge_at:
                        entry['span'] = merge_at[(ri, ci)]
                        entry['change_addrs'] = merge_changes[(ri, ci)]
                    data.append(entry)
                grid_rows.append({'index': ri, 'height': heights.get(ri, 15), 'cells': data,
                                  'added': ri in added or status == 'added'})
            removed = []
            if before and name in before.sheetnames and status != 'removed':
                for ri, cells in enumerate(before[name].iter_rows(max_col=max(cols, default=1)), 1):
                    if ri in removed_after and (removed_after[ri] in row_set or removed_after[ri] == 0):
                        removed.append({'index': ri, 'after': removed_after[ri], 'cells': [
                            {'addr': f'{get_column_letter(ci)}{ri}', 'value': value(cells[ci - 1])} for ci in cols]})
            columns = []
            for ci in cols:
                width = next((float(w.get('width', 13)) for w in widths if int(w['min']) <= ci <= int(w['max'])), 13)
                columns.append({'letter': get_column_letter(ci), 'width': max(36, min(600, width * 7 + 5))})
            limited = ws.max_row > len(rows) or ws.max_column > len(cols)
            result.append({'name': name, 'status': status, 'cols': columns, 'rows': grid_rows,
                           'merges': merges, 'changes': target_changes, 'removed_rows': removed,
                           'message': '표시 범위는 최대 2,000행 × 100열입니다. 변경 주변을 우선 표시하며 변경 목록에서 위치를 선택할 수 있습니다.' if limited else ''})
    return result
