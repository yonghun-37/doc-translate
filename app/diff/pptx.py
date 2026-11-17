from pathlib import Path

from pptx import Presentation

from app.diff.segments import compare
from app.storage import write_json


def _texts(path):
    result = {}
    if path is None:
        return result
    def walk(shapes, slide, prefix=''):
        for shape in shapes:
            name = prefix + shape.name
            if shape.has_text_frame:
                result[(slide, name, False)] = [p.text for p in shape.text_frame.paragraphs]
            if shape.has_table:
                result[(slide, name, False)] = [cell.text for row in shape.table.rows for cell in row.cells]
            if hasattr(shape, 'shapes'):
                walk(shape.shapes, slide, name + ' / ')
    for i, slide in enumerate(Presentation(path).slides, 1):
        walk(slide.shapes, i)
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
            result[(i, '발표자 노트', True)] = [p.text for p in slide.notes_slide.notes_text_frame.paragraphs]
    return result


def build(old: Path | None, new: Path, destination: Path):
    before, after = _texts(old), _texts(new)
    changes = []
    for key in dict.fromkeys([*before, *after]):
        slide, shape, notes = key
        for change in compare(before.get(key, []), after.get(key, [])):
            changes.append({**change, 'slide': slide, 'shape': shape, 'notes': notes})
    write_json(destination, changes)
