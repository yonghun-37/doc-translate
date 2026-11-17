from io import BytesIO
from zipfile import ZipFile, ZIP_DEFLATED

from docx import Document
from docx.shared import Inches
from lxml import etree
from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.drawing.image import Image as SheetImage
from PIL import Image
from pptx import Presentation
from pptx.util import Inches as SlideInches


def image_file(tmp_path):
    path = tmp_path/'sample.png'
    Image.new('RGB', (12, 12), (15, 20, 150)).save(path)
    return path


def rewrite_zip(path, changes):
    result = BytesIO()
    with ZipFile(path) as src, ZipFile(result, 'w', ZIP_DEFLATED) as dst:
        names = src.namelist()
        for info in src.infolist():
            dst.writestr(info, changes.get(info.filename, src.read(info.filename)))
        for name, value in changes.items():
            if name not in names:
                dst.writestr(name, value)
    path.write_bytes(result.getvalue())


def docx_file(path, body='기존 본문', *, rich=False, image=None, extra_parts=False):
    doc = Document()
    p = doc.add_paragraph()
    if rich:
        p.add_run('굵은 ').bold = True
        p.add_run(body).italic = True
        doc.add_paragraph().add_run('밑줄 텍스트').underline = True
    else:
        p.add_run(body)
    doc.add_paragraph('유지 문단')
    doc.add_table(rows=1, cols=1).cell(0, 0).text = '표 내용'
    doc.sections[0].header.paragraphs[0].text = '머리글'
    doc.sections[0].footer.paragraphs[0].text = '바닥글'
    doc.add_comment(p.runs, text='번역 금지 메모', author='검토자')
    if image:
        doc.add_picture(str(image), width=Inches(.25))
    doc.save(path)
    if extra_parts:
        w = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
        with ZipFile(path) as z:
            content = etree.fromstring(z.read('[Content_Types].xml'))
            rels = etree.fromstring(z.read('word/_rels/document.xml.rels'))
            main = etree.fromstring(z.read('word/document.xml'))
        # Real OOXML note parts linked into the document, plus a text box.
        changes = {}
        for tag, label in [('footnotes', '각주 내용'), ('endnotes', '미주 내용')]:
            part = etree.Element(f'{{{w}}}{tag}', nsmap={'w': w})
            note = etree.SubElement(part, f'{{{w}}}{tag[:-1]}', {f'{{{w}}}id': '1'})
            para = etree.SubElement(note, f'{{{w}}}p')
            run = etree.SubElement(para, f'{{{w}}}r')
            etree.SubElement(run, f'{{{w}}}t').text = label
            changes[f'word/{tag}.xml'] = etree.tostring(part)
            etree.SubElement(content, '{http://schemas.openxmlformats.org/package/2006/content-types}Override',
                PartName=f'/word/{tag}.xml', ContentType=f'application/vnd.openxmlformats-officedocument.wordprocessingml.{tag}+xml')
            etree.SubElement(rels, '{http://schemas.openxmlformats.org/package/2006/relationships}Relationship',
                Id=f'rId{tag}', Type=f'http://schemas.openxmlformats.org/officeDocument/2006/relationships/{tag}', Target=f'{tag}.xml')
        para = etree.SubElement(main.find(f'{{{w}}}body'), f'{{{w}}}p')
        run = etree.SubElement(para, f'{{{w}}}r')
        box = etree.SubElement(etree.SubElement(run, f'{{{w}}}pict'), f'{{{w}}}txbxContent')
        p = etree.SubElement(box, f'{{{w}}}p')
        r = etree.SubElement(p, f'{{{w}}}r')
        etree.SubElement(r, f'{{{w}}}t').text = '텍스트 상자'
        changes.update({'[Content_Types].xml': etree.tostring(content),
                        'word/_rels/document.xml.rels': etree.tostring(rels), 'word/document.xml': etree.tostring(main)})
        rewrite_zip(path, changes)
    return path


def xlsx_file(path, body='기존 셀', *, image=None):
    wb = Workbook()
    ws = wb.active
    ws.title = '원문 시트명'
    ws.append(['항목', '내용'])
    ws.append(['유지 셀', body])
    ws['A3'] = '=SUM(1,2)'
    ws['B3'] = 123
    ws['A2'].comment = Comment('번역 금지 메모', '검토자')
    ws.oddHeader.left.text = '회사명'
    ws.oddHeader.center.text = '&"Arial,Bold"&12설계서 &P / &N'
    ws.oddFooter.right.text = '바닥글 &D'
    ws.evenHeader.left.text = '짝수 머리글'
    ws.evenFooter.left.text = '짝수 바닥글'
    ws.firstHeader.left.text = '첫 머리글'
    ws.firstFooter.left.text = '첫 바닥글'
    if image:
        ws.add_image(SheetImage(str(image)), 'D2')
    wb.save(path)
    return path


def pptx_file(path, body='기존 제목', *, image=None):
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[1])
    slide.shapes.title.text = body
    slide.placeholders[1].text = '유지 본문'
    slide.notes_slide.notes_text_frame.text = '발표자 노트'
    if image:
        slide.shapes.add_picture(str(image), SlideInches(1), SlideInches(1))
    prs.save(path)
    return path
