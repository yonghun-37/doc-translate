"""Build exact-text reuse memory from uploaded original/Chinese documents."""
from collections import Counter
from difflib import SequenceMatcher
from itertools import groupby
from pathlib import Path

from openpyxl import load_workbook

from app import engine, xlsx_headers
from app.reuse_agent import needs_translation


def _groups(texts, locations):
    return [(where, [text for _, text in items])
            for where, items in groupby(zip(locations, texts), key=lambda item: item[0])]


def location_pairs(before, after):
    old, new = _groups(*before), _groups(*after)
    pairs = []
    matcher = SequenceMatcher(None, [key for key, _ in old], [key for key, _ in new], autojunk=False)
    for a, b, size in matcher.get_matching_blocks():
        for (_, source), (_, translated) in zip(old[a:a+size], new[b:b+size]):
            if len(source) == len(translated):
                pairs.extend(zip(source, translated))
    return pairs


def _string_cells(sheet):
    return {cell.coordinate: cell.value for row in sheet.iter_rows() for cell in row
            if isinstance(cell.value, str) and not cell.value.startswith('=') and cell.data_type != 'f'}


def cell_pairs(original: Path, translated: Path):
    before = load_workbook(original, read_only=True, data_only=False)
    try:
        after = load_workbook(translated, read_only=True, data_only=False)
        try:
            old_headers, new_headers = xlsx_headers.extract(original), xlsx_headers.extract(translated)
            pairs, locations = [], {}
            # Reserve all exact-name matches before using positional fallback.
            exact = set(before.sheetnames) & set(after.sheetnames)
            for index, source in enumerate(before.worksheets):
                target = after[source.title] if source.title in exact else (
                    after.worksheets[index] if index < len(after.worksheets)
                    and after.worksheets[index].title not in exact else None)
                old_cells = _string_cells(source)
                new_cells = _string_cells(target) if target is not None else {}
                for address, text in old_cells.items():
                    locations.setdefault(text, f'{source.title} · {address}')
                    if address in new_cells:
                        pairs.append((text, new_cells[address]))
                for (sheet, kind), source_texts in old_headers.items():
                    if sheet != source.title:
                        continue
                    for text in source_texts:
                        locations.setdefault(text, f'{sheet} · {kind}')
                    target_texts = new_headers.get((target.title, kind), []) if target is not None else []
                    if len(source_texts) == len(target_texts):
                        pairs.extend(zip(source_texts, target_texts))
            return pairs, locations
        finally:
            after.close()
    finally:
        before.close()


def memory_from_pairs(pairs):
    votes = {}
    for source, translated in pairs:
        if translated.strip() and source != translated:
            votes.setdefault(source, Counter())[translated] += 1
    # Counter preserves first-seen order for tied counts.
    return {source: counts.most_common(1)[0][0] for source, counts in votes.items()}


def build(original: Path, translated: Path, lang: str, *, source=None, target=None, logger=None):
    source = source if source is not None else engine.extract_with_locations(original, logger=logger)
    target = target if target is not None else engine.extract_with_locations(translated, logger=logger)
    texts, locations = source
    if original.suffix.lower() == '.xlsx':
        pairs, cell_locations = cell_pairs(original, translated)
        locations = [cell_locations.get(text, where) for text, where in zip(texts, locations)]
    else:
        pairs = location_pairs(source, target)
    memory = memory_from_pairs(pairs)
    unmatched = [{'where': where, 'text': text} for text, where in zip(texts, locations) if text not in memory]
    return memory, {'lang': lang, 'total': len(texts), 'matched': len(texts) - len(unmatched),
                    'unmatched_samples': unmatched[:20]}


def translation_plan(segments, memory):
    eligible = [text for text in segments if needs_translation(text)]
    return {'segments': len(segments), 'reused': sum(text in memory for text in eligible),
            'translated': len({text for text in eligible if text not in memory})}
