"""Independent upload jobs; inputs are write-once and publication is atomic."""
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import os
from pathlib import Path
import shutil
import tempfile
import threading
import uuid

from app.config import Config, LANGUAGES
from app import alignment, engine
from app.diagnostics import library_logger, safe_error
from app.diff import docx, xlsx, pptx
from app.diff.segments import compare
from app.reuse_agent import ReuseAgent
from app.storage import Storage, now, read_json, write_json
from app.inputs import display_filename, validate_package


class StateError(ValueError):
    pass


class InvalidUpload(ValueError):
    pass


class Pipeline:
    def __init__(self, root: Path, *, config: Config | None = None, agent_factory=None):
        self.store = Storage(root)
        self.config = config or Config.load(self.store.root)
        self.agent_factory = agent_factory or self.config.make_agent
        self._mutex = threading.RLock()
        self.logger = library_logger(self.store.root)

    @contextmanager
    def _locked(self):
        with self._mutex, self.store.path('logs', '.pipeline.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def upload(self, files: dict[str, tuple[Path, str]], *, title=None, by=None):
        """Files use storage role names; callers retain ownership of temporary inputs."""
        if 'revised' not in files or set(files) - {'original', 'revised', 'base_zh-CN', 'base_zh-TW'}:
            raise InvalidUpload('수정본은 필수이며 지정된 네 파일만 올릴 수 있습니다.')
        try:
            names = {role: display_filename(name) for role, (_, name) in files.items()}
        except ValueError as exc:
            raise InvalidUpload(str(exc)) from None
        ext = Path(names['revised']).suffix.lower().lstrip('.')
        if any(Path(name).suffix.lower() != f'.{ext}' for name in names.values()):
            raise InvalidUpload('모든 파일의 확장자는 수정본과 같아야 합니다.')
        if len((title or '').strip()) > 240 or len((by or '').strip()) > 200:
            raise InvalidUpload('제목은 240자, 이름은 200자 이내로 입력하세요.')
        try:
            for path, _ in files.values():
                validate_package(path, ext)
        except Exception:
            raise InvalidUpload('올바른 Office ZIP 문서가 아닙니다.') from None
        if 'original' in files and self._hash(files['original'][0]) == self._hash(files['revised'][0]):
            raise InvalidUpload('원본과 수정본의 내용이 바이트 단위로 동일합니다.')
        with self._locked():
            job_id = self._new_id()
            state = {
                'id': job_id, 'title': (title or '').strip() or names['revised'], 'ext': ext,
                'status': 'pending', 'created_at': now(), 'uploaded_by': (by or '').strip() or None,
                'decided_at': None, 'decided_by': None, 'reason': None, 'error': None,
                'files': names, 'counts': {}, 'alignment': {}, 'stats': {}, 'outputs': {},
            }
            staging_root = self.store.path('logs', '.uploads')
            staging_root.mkdir(exist_ok=True)
            try:
                with tempfile.TemporaryDirectory(prefix='register-', dir=staging_root) as temp:
                    staged = Path(temp) / job_id
                    (staged / 'inputs').mkdir(parents=True)
                    (staged / 'review').mkdir()
                    for role, (path, _) in files.items():
                        shutil.copyfile(path, staged / 'inputs' / f'{role}.{ext}')
                    self._prepare(state, staged)
                    write_json(staged / 'status.json', state)
                    self.store.event('registered', id=job_id, status='pending')
                    # The entire job becomes visible in one rename; inputs never move again.
                    os.replace(staged, self.store.job_dir(job_id))
            except Exception as exc:
                code, message = safe_error(exc)
                raise InvalidUpload(f'문서 검토를 준비할 수 없습니다 — {code}: {message}') from None
            return state

    def _new_id(self):
        while True:
            job_id = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-') + uuid.uuid4().hex[:6]
            if not self.store.job_dir(job_id).exists():
                return job_id

    @staticmethod
    def _hash(path):
        with path.open('rb') as handle:
            return hashlib.file_digest(handle, 'sha256').hexdigest()

    def _prepare(self, state, folder):
        ext = state['ext']
        inputs, review = folder / 'inputs', folder / 'review'
        revised = inputs / f'revised.{ext}'
        # Every supplied document is extracted, even an unused base without an original.
        extracted = {role: engine.extract_with_locations(inputs / f'{role}.{ext}', logger=self.logger)
                     for role in state['files']}
        before = extracted.get('original')
        after = extracted['revised']
        changes = compare(before[0], after[0], before[1], after[1]) if before is not None else []
        write_json(review / 'changes.json', changes)
        counts = Counter(change['op'] for change in changes)
        state['counts'] = {op: counts[op] for op in ('added', 'removed', 'modified')}
        if before is not None:
            self._build_diff(inputs / f'original.{ext}', revised, review, ext)
        details, plans = {}, {}
        for lang in LANGUAGES:
            memory = {}
            role = f'base_{lang}'
            if role in extracted:
                if before is not None:
                    memory, details[lang] = alignment.build(
                        inputs / f'original.{ext}', inputs / f'{role}.{ext}', lang,
                        source=before, target=extracted[role], logger=self.logger)
                else:
                    details[lang] = {'lang': lang, 'total': 0, 'matched': 0, 'unmatched_samples': []}
                state['alignment'][lang] = {k: details[lang][k] for k in ('total', 'matched')}
            write_json(review / f'memory_{lang}.json', memory)
            plans[lang] = alignment.translation_plan(after[0], memory)
        write_json(review / 'alignment.json', details)
        write_json(review / 'plan.json', plans)

    def _build_diff(self, original, revised, directory, ext):
        if ext == 'docx':
            docx.build(original, revised, directory / 'redline.docx', cache_dir=self.store.path('logs', '.docxodus'))
        elif ext == 'xlsx':
            xlsx.build_json(original, revised, directory / 'sheets.json')
        else:
            pptx.build(original, revised, directory / 'slides.json')

    def start_translation(self, job_id, by=None, *, background=False):
        with self._locked():
            state = self.store.read_status(job_id)
            if state['status'] != 'pending':
                raise StateError('검토 대기 상태에서만 번역을 실행할 수 있습니다.')
            state.update(status='translating', decided_at=now(), decided_by=(by or '').strip() or None,
                         reason=None, error=None)
            self.store.save_status(state)
            return state if background else self._translate_locked(state)

    def reject(self, job_id, reason, by=None):
        if not reason or not reason.strip():
            raise StateError('반려 사유를 입력하세요.')
        with self._locked():
            state = self.store.read_status(job_id)
            if state['status'] != 'pending':
                raise StateError('검토 대기 상태에서만 반려할 수 있습니다.')
            state.update(status='rejected', decided_at=now(), decided_by=(by or '').strip() or None, reason=reason.strip())
            self.store.save_status(state)
            return state

    def retry(self, job_id, *, background=False):
        with self._locked():
            state = self.store.read_status(job_id)
            if state['status'] != 'failed':
                raise StateError('실패 상태에서만 재시도할 수 있습니다.')
            state.update(status='translating', error=None)
            self.store.save_status(state)
            return state if background else self._translate_locked(state)

    def translate(self, job_id):
        with self._locked():
            state = self.store.read_status(job_id)
            if state['status'] != 'translating':
                raise StateError('예약된 번역 작업이 아닙니다.')
            return self._translate_locked(state)

    def delete(self, job_id):
        # Reject immediately while the translator holds the long-running lock.
        if self.store.read_status(job_id)['status'] == 'translating':
            raise StateError('번역 중인 작업은 삭제할 수 없습니다.')
        with self._locked():
            if self.store.read_status(job_id)['status'] == 'translating':
                raise StateError('번역 중인 작업은 삭제할 수 없습니다.')
            shutil.rmtree(self.store.job_dir(job_id))
            self.store.event('deleted', id=job_id)

    def _translate_locked(self, state):
        job_id, ext = state['id'], state['ext']
        folder = self.store.job_dir(job_id)
        destination = folder / 'output'
        try:
            with tempfile.TemporaryDirectory(prefix='.work-', dir=folder) as temp:
                staging = Path(temp) / 'output'
                staging.mkdir()
                outputs, stats = {}, {}
                for lang in LANGUAGES:
                    memory = read_json(folder / 'review' / f'memory_{lang}.json')
                    agent = ReuseAgent(memory, self.agent_factory(lang))
                    output = engine.translate(folder / 'inputs' / f'revised.{ext}', agent, logger=self.logger)
                    name = f"{Path(state['files']['revised']).stem}_{lang}.{ext}"
                    staged = staging / name
                    staged.write_bytes(output)
                    validate_package(staged, ext)
                    outputs[lang] = f'output/{name}'
                    stats[lang] = agent.stats
                    self.store.event('translation', id=job_id, lang=lang, **agent.stats)
                os.replace(staging, destination)
                state.update(status='translated', outputs=outputs, stats=stats, error=None)
                self.store.save_status(state)
            return state
        except BaseException as exc:
            if destination.exists():
                shutil.rmtree(destination)
            code, message = safe_error(exc)
            state.update(status='failed', outputs={}, stats={}, error=f'번역 실패 — {code}: {message}')
            self.store.save_status(state)
            self.store.event('failure', id=job_id, code=code, message=message)
            if not isinstance(exc, Exception):
                raise
            return state
