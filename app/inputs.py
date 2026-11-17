import zipfile
from pathlib import Path

from lxml import etree

def display_filename(name: str) -> str:
    name = name.replace('\\', '/').rsplit('/', 1)[-1]
    if (not name or any(ord(c) < 32 or ord(c) == 127 for c in name)
            or len(name.encode('utf-8')) > 240):
        raise ValueError('파일명이 비어 있거나 너무 길거나 제어 문자가 포함되어 있습니다.')
    if Path(name).suffix.lower() not in {'.docx', '.xlsx', '.pptx'}:
        raise ValueError('docx·xlsx·pptx 파일만 올릴 수 있습니다.')
    return name


def validate_package(path: Path, ext: str):
    main = {'docx': 'word/document.xml', 'xlsx': 'xl/workbook.xml', 'pptx': 'ppt/presentation.xml'}[ext]
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() or not {'[Content_Types].xml', '_rels/.rels', main}.issubset(archive.namelist()):
            raise ValueError('올바른 Office ZIP 문서가 아닙니다.')
        # XLSX's upstream extractor need not read workbook.xml, and can therefore
        # miss malformed parts. Validate package XML before any job is published.
        for name in archive.namelist():
            if name.endswith(('.xml', '.rels')):
                with archive.open(name) as part:
                    etree.parse(part, etree.XMLParser(resolve_entities=False, no_network=True))

