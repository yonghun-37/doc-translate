import json
import os
import re
import tempfile
import fcntl
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat()


def safe_job_id(job_id: str):
    if not re.fullmatch(r'[0-9]{8}-[0-9]{6}-[0-9a-f]{6}', job_id):
        raise ValueError('올바르지 않은 작업 ID입니다.')
    return job_id


def atomic_write(path: Path, content: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.tmp-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def write_json(path: Path, value):
    atomic_write(path, (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode())


def read_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


class Storage:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        for name in ('jobs', 'logs'):
            self.path(name).mkdir(parents=True, exist_ok=True)

    def path(self, *parts):
        path = self.root.joinpath(*parts)
        if not path.resolve().is_relative_to(self.root):
            raise ValueError('허용되지 않은 경로입니다.')
        return path

    def job_dir(self, job_id):
        directory = self.path('jobs', safe_job_id(job_id))
        if any(p.is_symlink() for p in [directory, *directory.parents]):
            raise ValueError('허용되지 않은 경로입니다.')
        return directory

    def read_status(self, job_id):
        return read_json(self.job_dir(job_id) / 'status.json')

    def statuses(self):
        states = []
        for directory in self.path('jobs').iterdir():
            try:
                states.append(self.read_status(directory.name))
            except (FileNotFoundError, ValueError):
                continue
        return sorted(states, key=lambda s: (s['created_at'], s['id']), reverse=True)

    def save_status(self, state):
        with self.status_locked():
            path = self.job_dir(state['id']) / 'status.json'
            current = read_json(path) if path.exists() else {}
            # Rendering owns preview independently of long-running translation.
            if 'preview' in current:
                state['preview'] = current['preview']
            write_json(self.job_dir(state['id']) / 'status.json', state)
        self.event('state', id=state['id'], status=state['status'])

    @contextmanager
    def status_locked(self):
        with self.path('logs', '.status.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def update_status(self, job_id, **fields):
        with self.status_locked():
            state = self.read_status(job_id)  # Never recreate deleted jobs.
            state.update(fields)
            write_json(self.job_dir(job_id) / 'status.json', state)
            return state

    def event(self, event, **fields):
        # Call sites pass metadata only, only sanitized diagnostic summaries, never text segments.
        line = json.dumps({'at': now(), 'event': event, **fields}, ensure_ascii=False) + '\n'
        with self.path('logs', 'events.jsonl').open('a', encoding='utf-8') as handle:
            handle.write(line)
