"""Office I/O delegated to pinned docutranslate translators."""
from pathlib import Path

from docx.parts.story import StoryPart

from docutranslate.ir.document import Document
from docutranslate.translator.ai_translator.docx_translator import DocxTranslator, DocxTranslatorConfig
from docutranslate.translator.ai_translator.xlsx_translator import XlsxTranslator, XlsxTranslatorConfig
from docutranslate.translator.ai_translator.pptx_translator import PPTXTranslator, PPTXTranslatorConfig

from app.config import QUIET_LOGGER
from app.reuse_agent import FakeAgent
from app.xlsx_headers import transform


class NotesDocxTranslator(DocxTranslator):
    """Expose generic note parts to the upstream traversal and writer."""

    def _pre_translate(self, document):
        doc, elements, texts = super()._pre_translate(document)
        for rel in list(doc.part.rels.values()):
            kind = rel.reltype.rsplit('/', 1)[-1]
            if rel.is_external or kind not in {'footnotes', 'endnotes'}:
                continue
            if getattr(doc.part, f'{kind}_part', None) is not None:
                continue
            original = rel.target_part
            note = StoryPart.load(original.partname, original.content_type, original.blob, original.package)
            for child in original.rels.values():
                note.load_rel(child.reltype, child.target_ref if child.is_external else child.target_part,
                              child.rId, child.is_external)
            doc.part.load_rel(rel.reltype, note, rel.rId)
            self._traverse_container(note, elements, texts)
        return doc, elements, texts


_TRANSLATORS = {
    '.docx': (NotesDocxTranslator, DocxTranslatorConfig),
    '.xlsx': (XlsxTranslator, XlsxTranslatorConfig),
    '.pptx': (PPTXTranslator, PPTXTranslatorConfig),
}


def translate(path: Path, agent, *, logger=None) -> bytes:
    path = Path(path)
    cls, config_cls = _TRANSLATORS[path.suffix.lower()]
    translator = cls(config_cls(skip_translate=True, glossary_generate_enable=False, logger=logger or QUIET_LOGGER))
    translator.translate_agent = agent
    document = Document.from_path(path)
    translator.translate(document)
    if path.suffix.lower() == '.xlsx':
        document.content = transform(document.content, agent, translator.chunk_size)
    return document.content


def extract(path: Path, *, logger=None) -> list[str]:
    agent = FakeAgent('source', identity=True)
    translate(path, agent, logger=logger)
    texts = [text for call in agent.calls for text in call]
    # Upstream XLSX uses a set: its iteration order is not document order.
    # Cell locations and row movement are represented by the daff report.
    return sorted(texts) if Path(path).suffix.lower() == '.xlsx' else texts


def extract_with_locations(path: Path, *, logger=None) -> tuple[list[str], list[str]]:
    from app.locations import docx_location, pptx_locations
    path = Path(path)
    if path.suffix.lower() == '.xlsx':
        texts = extract(path, logger=logger)
        return texts, [f'세그먼트 {i}' for i in range(1, len(texts) + 1)]
    cls, config_cls = _TRANSLATORS[path.suffix.lower()]
    translator = cls(config_cls(skip_translate=True, glossary_generate_enable=False, logger=logger or QUIET_LOGGER))
    doc, elements, texts = translator._pre_translate(Document.from_path(path))
    labels = [docx_location(info) for info in elements] if path.suffix.lower() == '.docx' else pptx_locations(doc, elements)
    return texts, [label or f'세그먼트 {i}' for i, label in enumerate(labels, 1)]
