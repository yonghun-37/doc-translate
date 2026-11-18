"""Patch only worksheet headerFooter XML; leave every other ZIP part untouched."""
from io import BytesIO
from pathlib import Path
import posixpath
import re
from zipfile import ZipFile

from lxml import etree

_NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
_FIELDS = {'oddHeader', 'oddFooter', 'evenHeader', 'evenFooter', 'firstHeader', 'firstFooter'}
# Formatting, alignment, dynamic fields, and escaped ampersands are opaque tokens.
_CONTROL = re.compile(r'(&(?:"[^"]*"|K[0-9A-Fa-f]{6}|K\d{2}[+\-]\d{3}|\d+|\[[^\]]+\]|.))')


def _xml(content):
    return etree.fromstring(content, etree.XMLParser(resolve_entities=False, no_network=True))


def _parts(src):
    parts, segments = [], []
    for name in src.namelist():
        if not re.fullmatch(r'xl/worksheets/[^/]+\.xml', name):
            continue
        root = _xml(src.read(name))
        fields = []
        for node in root.findall(f'{{{_NS}}}headerFooter/*'):
            if etree.QName(node).localname not in _FIELDS or not node.text:
                continue
            tokens = _CONTROL.split(node.text)
            replacements = []
            for i in range(0, len(tokens), 2):
                text = tokens[i]
                stripped = text.strip()
                if stripped:
                    replacements.append((i, len(segments), text[:len(text)-len(text.lstrip())], text[len(text.rstrip()):]))
                    segments.append(stripped)
            fields.append((node, tokens, replacements))
        if fields:
            parts.append((name, root, fields))
    return parts, segments


def extract(path: Path) -> dict[tuple[str, str], list[str]]:
    """Use the writer's tokenization, keyed by actual worksheet and field kind."""
    with ZipFile(path) as src:
        rels = {rel.get('Id'): posixpath.normpath('xl/' + rel.get('Target')).lstrip('/')
                if not rel.get('Target').startswith('/') else rel.get('Target').lstrip('/')
                for rel in _xml(src.read('xl/_rels/workbook.xml.rels'))
                if rel.get('TargetMode') != 'External'}
        sheets = {rels[sheet.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')]: sheet.get('name')
                  for sheet in _xml(src.read('xl/workbook.xml')).findall(f'{{{_NS}}}sheets/*')}
        parts, segments = _parts(src)
        return {(sheets[name], etree.QName(node).localname): [segments[pos] for _, pos, _, _ in replacements]
                for name, _, fields in parts for node, _, replacements in fields}


def located(path: Path):
    """Keep the shared header tokenizer while distinguishing left/center/right."""
    with ZipFile(path) as src:
        rels = {rel.get('Id'): posixpath.normpath('xl/' + rel.get('Target')).lstrip('/')
                if not rel.get('Target').startswith('/') else rel.get('Target').lstrip('/')
                for rel in _xml(src.read('xl/_rels/workbook.xml.rels')) if rel.get('TargetMode') != 'External'}
        sheets = {rels[s.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')]: s.get('name')
                  for s in _xml(src.read('xl/workbook.xml')).findall(f'{{{_NS}}}sheets/*')}
        parts, _ = _parts(src)
        result = {}
        for name, _, fields in parts:
            for node, tokens, _ in fields:
                field = etree.QName(node).localname
                kind = '머리글' if field.endswith('Header') else '바닥글'
                variant = '짝수 ' if field.startswith('even') else '첫 페이지 ' if field.startswith('first') else ''
                side, chunks = '가운데', {}
                for i, token in enumerate(tokens):
                    if i % 2:
                        side = {'&L': '왼쪽', '&C': '가운데', '&R': '오른쪽'}.get(token, side)
                    elif token.strip():
                        chunks.setdefault(side, []).append(token.strip())
                for side, texts in chunks.items():
                    result[(sheets[name], f'{variant}{kind}({side})')] = ' '.join(texts)
        return result


def transform(content: bytes, agent, chunk_size: int = 3000) -> bytes:
    with ZipFile(BytesIO(content)) as src:
        parts, segments = _parts(src)
        if not segments:
            return content
        translated = agent.send_segments(segments, chunk_size)
        if len(translated) != len(segments):
            raise ValueError('머리글·바닥글 번역 개수가 다릅니다.')
        changed = {}
        for name, root, fields in parts:
            dirty = False
            for node, tokens, replacements in fields:
                for index, pos, prefix, suffix in replacements:
                    tokens[index] = prefix + translated[pos].replace('&', '&&') + suffix
                new_text = ''.join(tokens)
                dirty |= new_text != node.text
                node.text = new_text
            if dirty:
                changed[name] = etree.tostring(root, encoding='utf-8', xml_declaration=True)
        if not changed:
            return content
        result = BytesIO()
        with ZipFile(result, 'w') as dst:
            dst.comment = src.comment
            for info in src.infolist():
                dst.writestr(info, changed.get(info.filename, src.read(info.filename)))
        return result.getvalue()
