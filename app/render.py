"""External LibreOffice conversion and bounded PDFium page images, without a shell."""
from contextlib import closing, contextmanager
import fcntl
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import tempfile
import threading
import uuid

import pypdfium2 as pdfium

from app.storage import read_json, write_json
from app.slide_layout import overlays

_RENDER_LOCK = threading.Lock()
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


class RenderTimeout(RuntimeError):
    pass


def find_soffice(config):
    candidates = [os.environ.get('DOC_TRANSLATE_SOFFICE', ''), config.soffice,
                  shutil.which('soffice'), shutil.which('libreoffice'),
                  *sorted(Path('/opt').glob('libreoffice*/program/soffice'))]
    for candidate in candidates:
        if candidate:
            path = Path(candidate).expanduser()
            if path.is_file() and os.access(path, os.X_OK):
                return path.resolve()
    return None


@contextmanager
def render_lock(logs):
    with _RENDER_LOCK, (logs / '.render.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def convert(source, destination, executable, config, logs):
    profile = logs / '.lo-profile' / uuid.uuid4().hex
    profile.mkdir(parents=True)
    destination.mkdir(parents=True, exist_ok=True)
    try:
        args = [str(executable), '--headless', '--norestore', '--nolockcheck',
                '-env:UserInstallation=' + profile.resolve().as_uri(), '--convert-to', 'pdf',
                '--outdir', str(destination), str(source)]
        process = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   start_new_session=True)
        try:
            returncode = process.wait(timeout=config.timeout_sec)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            raise RenderTimeout() from None
        except BaseException:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            raise
        pdf = destination / (source.stem + '.pdf')
        if returncode != 0 or not pdf.is_file():
            raise RuntimeError('PDF 변환 실패')
        return pdf
    finally:
        shutil.rmtree(profile, ignore_errors=True)


def rasterize(pdf, directory, prefix, max_pages):
    pages, texts = [], []
    with pdfium.PdfDocument(pdf) as document:
        total = len(document)
        for index in range(min(total, max_pages)):
            with closing(document[index]) as page:
                width, height = page.get_size()
                with closing(page.get_textpage()) as text:
                    texts.append(text.get_text_range())
                with closing(page.render(scale=1600 / max(width, height))) as bitmap:
                    name = f'{prefix}-{index + 1:03d}.png'
                    bitmap.to_pil().save(directory / name)
                    pages.append({'page': index + 1, 'name': name,
                                  'width': bitmap.width, 'height': bitmap.height, 'side': prefix})
    return pages, texts, total


def normalize(text):
    return re.sub(r'\s+', '', text)


def locate_pages(changes, texts, paragraphs=None):
    """Search forward, including unchanged paragraphs to disambiguate repetitions."""
    normalized = [normalize(text) for text in texts]
    page, offset, ordinals = 0, 0, {}
    locations = {}
    # paragraphs carry the full revision order and labels for both source versions.
    entries = paragraphs if paragraphs is not None else [
        {'text': c.get('new') or c.get('old') or '', 'keys': [(c['where'], c.get('new') or c.get('old') or '')]}
        for c in changes if c['where'].startswith('본문')]
    for entry in entries:
        needles = list(dict.fromkeys(normalize(value) for value in
                       [entry['text'], *[key[1] for key in entry['keys']]] if normalize(value)))
        if not needles:
            continue
        found = None
        for pi in range(page, len(normalized)):
            for needle in needles:
                position = normalized[pi].find(needle, offset if pi == page else 0)
                if position >= 0:
                    found = pi, position + len(needle)
                    break
            if found:
                break
        if found is None:
            continue
        page, offset = found
        ordinals[page] = ordinals.get(page, 0) + 1
        for key in entry['keys']:
            locations.setdefault(key, []).append((page + 1, ordinals[page]))
    for change in changes:
        where = change['where']
        if not where.startswith('본문'):
            continue
        text = change.get('new') or change.get('old') or ''
        matches = locations.get((where, text), [])
        if not matches:
            matches = next((positions for (label, paragraph), positions in locations.items()
                            if label == where and normalize(text) and normalize(text) in normalize(paragraph)), [])
        if not matches:
            continue
        number, ordinal = matches.pop(0) if len(matches) > 1 else matches[0]
        change['page'] = number
        if '표 ' in where:
            suffix = where.split('표 ', 1)[1].replace('·', ' · ')
            change['where'] = f'{number}페이지 · 표 {suffix}'
        elif '텍스트 상자' in where:
            change['where'] = f'{number}페이지 · 텍스트 상자'
        else:
            change['where'] = f'{number}페이지 · {ordinal}번째 문단'
    return changes


def docx_paragraphs(path):
    # Number original/revised paragraphs separately: paragraph insertions/deletions
    # are tracked in pPr/rPr; run edits do not change paragraph numbering.
    from docx import Document
    from docx.text.paragraph import Paragraph
    from app.locations import docx_location
    doc = Document(path)
    result, old_number, new_number = [], 0, 0
    for element in doc.element.body.iter(W + 'p'):
        if any(a.tag == W + 'txbxContent' for a in element.iterancestors()):
            continue
        paragraph = Paragraph(element, doc)
        label = docx_location({'paragraph': paragraph})
        in_table = any(a.tag == W + 'tc' for a in element.iterancestors())
        deleted = element.find(f'{W}pPr/{W}rPr/{W}del') is not None
        inserted = element.find(f'{W}pPr/{W}rPr/{W}ins') is not None
        old_text = ''.join(n.text or '' for n in element.iter() if n.tag in {W + 't', W + 'delText'}
                           and not any(a.tag == W + 'ins' for a in n.iterancestors()))
        new_text = ''.join(n.text or '' for n in element.iter(W + 't')
                           if not any(a.tag == W + 'del' for a in n.iterancestors()))
        full = ''.join(n.text or '' for n in element.iter() if n.tag in {W + 't', W + 'delText'})
        keys = []
        if not in_table:
            if not inserted:
                old_number += 1
                keys.append((f'본문 문단 {old_number}', old_text))
            if not deleted:
                new_number += 1
                keys.append((f'본문 문단 {new_number}', new_text))
        else:
            keys = [(label, old_text), (label, new_text)]
        result.append({'text': full, 'keys': list(dict.fromkeys(keys))})
    return result


def prepare(store, job_id, config):
    """Publish only after rendering succeeds; never hold the pipeline lock."""
    try:
        state = store.read_status(job_id)
        if state.get('preview', {}).get('status') != 'pending':
            return
        executable = find_soffice(config)
        if executable is None:
            store.update_status(job_id, preview={'status': 'unavailable', 'message':
                '서버에 LibreOffice가 없어 원래 모양 보기를 할 수 없습니다', 'pages': []})
            return
        logs, folder = store.path('logs'), store.job_dir(job_id)
        with render_lock(logs), tempfile.TemporaryDirectory(prefix='.render-', dir=logs) as temp:
            work = Path(temp)
            preview = work / 'preview'
            preview.mkdir()
            state = store.read_status(job_id)
            if state.get('preview', {}).get('status') != 'pending':
                return
            ext = state['ext']
            pages, message = [], ''
            changed = read_json(folder / 'review/changes.json')
            sources = [('redline', folder / 'review/redline.docx')] if ext == 'docx' else [
                ('original', folder / 'inputs/original.pptx'), ('revised', folder / 'inputs/revised.pptx')]
            copies = {}
            for prefix, source in sources:
                copy = work / source.name
                shutil.copyfile(source, copy)
                copies[prefix] = copy
                pdf = convert(copy, work / 'pdf', executable, config, logs)
                rendered, texts, total = rasterize(pdf, preview, prefix, config.max_pages)
                pages.extend(rendered)
                if total > config.max_pages:
                    message = f'문서당 최대 {config.max_pages}페이지만 표시합니다. 초과 페이지는 변경 목록에서 확인하세요.'
                if ext == 'docx':
                    locate_pages(changed, texts, docx_paragraphs(copy))
            if ext == 'pptx':
                write_json(preview / 'overlays.json', overlays(copies['original'], copies['revised'],
                           read_json(folder / 'review/slides.json')))
            # Deletion and publication share this short lock. Translation progress
            # merges status fields under the same lock, avoiding stale snapshots.
            with store.status_locked():
                latest = store.read_status(job_id)
                os.replace(preview, folder / 'review/preview')
                if ext == 'docx':
                    os.replace(work / 'pdf/redline.pdf', folder / 'review/redline.pdf')
                    write_json(folder / 'review/changes.json', changed)
                latest['preview'] = {'status': 'ready', 'message': message, 'pages': pages}
                write_json(folder / 'status.json', latest)
    except FileNotFoundError:
        # If the job was deleted, there is deliberately nothing left to update.
        _failure(store, job_id, '미리보기 파일을 읽을 수 없습니다. 변경 목록을 이용하세요.')
    except Exception as exc:
        _failure(store, job_id, '미리보기 시간 제한을 초과했습니다. 변경 목록을 이용하세요.'
                 if isinstance(exc, RenderTimeout) else '미리보기를 만들지 못했습니다. 변경 목록을 이용하세요.')


def _failure(store, job_id, message):
    try:
        store.update_status(job_id, preview={'status': 'failed', 'message': message, 'pages': []})
    except FileNotFoundError:
        pass
