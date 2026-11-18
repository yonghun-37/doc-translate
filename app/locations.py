"""Label upstream extraction elements; never extract or rewrite their text."""
from lxml import etree

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
P = '{http://schemas.openxmlformats.org/presentationml/2006/main}'
A = '{http://schemas.openxmlformats.org/drawingml/2006/main}'


def shape_label(element, paragraph=None):
    if paragraph is not None:
        cell = next((a for a in paragraph.iterancestors() if a.tag == A + 'tc'), None)
        if cell is not None:
            row = cell.getparent()
            return f'표 {list(row.getparent().iterchildren(A + "tr")).index(row) + 1}행 {list(row.iterchildren(A + "tc")).index(cell) + 1}열'
    placeholder = next(element.iter(P + 'ph'), None)
    if placeholder is not None:
        kind = placeholder.get('type', 'obj')
        if kind in {'title', 'ctrTitle'}:
            return '제목'
        if kind in {'body', 'obj', 'subTitle'}:
            return '본문'
    props = next(element.iter(P + 'cNvPr'), None)
    return f'도형 "{props.get("name", "") if props is not None else ""}"'


def docx_location(info: dict) -> str | None:
    paragraph = info.get('paragraph')
    if paragraph is None:
        return None
    element = paragraph._p
    root = element.getroottree().getroot()
    kind = etree.QName(root).localname
    prefix = {'hdr': '머리글', 'ftr': '바닥글', 'footnotes': '각주', 'endnotes': '미주'}.get(kind, '본문')
    ancestors = list(element.iterancestors())
    if any(a.tag == W + 'txbxContent' for a in ancestors):
        top = info.get('top_level_paragraph')
        base = docx_location({'paragraph': top}) if top is not None and top._p is not element else prefix
        return f'{base or prefix} · 텍스트 상자'
    cell = next((a for a in ancestors if a.tag == W + 'tc'), None)
    if cell is not None:
        row = cell.getparent()
        table = row.getparent()
        tables = list(root.iter(W + 'tbl'))
        if table in tables:
            r = list(table.iterchildren(W + 'tr')).index(row) + 1
            c = 1
            for sibling in row.iterchildren(W + 'tc'):
                if sibling is cell:
                    break
                span = sibling.find(f'{W}tcPr/{W}gridSpan')
                c += int(span.get(W + 'val', '1')) if span is not None else 1
            return f'{prefix} 표 {tables.index(table) + 1}·{r}행 {c}열'
    if kind in {'footnotes', 'endnotes'}:
        note = next((a for a in ancestors if a.tag in {W + 'footnote', W + 'endnote'}), None)
        return f'{prefix} {note.get(W + "id", "")}' if note is not None else prefix
    paragraphs = [p for p in root.iter(W + 'p') if not any(a.tag in {W + 'tc', W + 'txbxContent'} for a in p.iterancestors())]
    return f'{prefix} 문단 {paragraphs.index(element) + 1}' if element in paragraphs else prefix


def pptx_locations(presentation, elements: list[dict]) -> list[str | None]:
    roots = {}
    for n, slide in enumerate(presentation.slides, 1):
        roots[slide.element] = f'슬라이드 {n}'
        if slide.has_notes_slide:
            roots[slide.notes_slide.element] = f'슬라이드 {n} · 발표자 노트'
    for n, master in enumerate(presentation.slide_masters, 1):
        roots[master.element] = f'마스터 {n}'
        for m, layout in enumerate(master.slide_layouts, 1):
            roots[layout.element] = f'마스터 {n} · 레이아웃 {m}'
    labels = []
    for info in elements:
        para = info.get('paragraph')
        if para is None:
            labels.append(None)
            continue
        element = para._p
        label = roots.get(element.getroottree().getroot())
        shape = next((a for a in element.iterancestors() if a.tag in {P + 'sp', P + 'graphicFrame'}), None)
        if label and shape is not None and '발표자 노트' not in label:
            label += ' · ' + shape_label(shape, element)
        labels.append(label)
    return labels
