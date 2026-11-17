from io import BytesIO
from pathlib import Path

from docx import Document
from python_redlines.engines import DocxodusEngine

from app.storage import atomic_write


def build(old: Path | None, new: Path, destination: Path, *, cache_dir: Path):
    if old is None:
        empty = BytesIO()
        Document().save(empty)
        original = empty.getvalue()
    else:
        original = old.read_bytes()
    engine = DocxodusEngine(target_path=str(cache_dir))
    result, _, _ = engine.run_redline('doc-translate', original, new.read_bytes())
    atomic_write(destination, result)
