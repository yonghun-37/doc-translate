"""Bound multipart parsing while receiving, with request-scoped disk staging."""
from contextlib import asynccontextmanager
from pathlib import Path
import tempfile

from fastapi import HTTPException, Request
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartException, MultiPartParser


class UploadParser(MultiPartParser):
    def __init__(self, headers, stream, directory, max_bytes):
        super().__init__(headers, stream, max_files=4, max_fields=2, max_part_size=16 * 1024)
        self.directory = directory
        self.max_bytes = max_bytes
        self.file_bytes = 0
        self.complete = False

    def on_headers_finished(self):
        super().on_headers_finished()
        part = self._current_part
        self.file_bytes = 0
        if part.file is not None:
            # Reuse Starlette's parser and async file writes, but put every byte
            # on disk under logs/.uploads rather than a global spooled temp file.
            source_name = (part.file.filename or '').replace('\\', '/').rsplit('/', 1)[-1]
            ext = Path(source_name).suffix.lower()
            if ext not in {'.docx', '.xlsx', '.pptx'}:
                raise MultiPartException('지원하지 않는 확장자입니다.')
            handle = tempfile.NamedTemporaryFile(dir=self.directory, suffix=ext, delete=False)
            part.file.file.close()
            self._files_to_close_on_error[-1] = handle
            part.file = UploadFile(file=handle, size=0, filename=source_name, headers=part.file.headers)

    def on_part_data(self, data, start, end):
        if self._current_part.file is not None:
            self.file_bytes += end - start
            if self.file_bytes > self.max_bytes:
                raise HTTPException(413, '업로드 파일 크기 한도를 초과했습니다.')
        super().on_part_data(data, start, end)

    def on_end(self):
        self.complete = True


@asynccontextmanager
async def upload_form(request: Request, staging_root: Path, max_bytes: int):
    if request.headers.get('content-type', '').split(';', 1)[0].strip().lower() != 'multipart/form-data':
        raise HTTPException(400, 'multipart 형식으로 문서를 올려 주세요.')
    # File bytes have their own exact limit; bound metadata and framing as well.
    body_limit = 4 * max_bytes + 64 * 1024

    async def stream():
        received = 0
        async for chunk in request.stream():
            received += len(chunk)
            if received > body_limit:
                raise HTTPException(413, '업로드 요청 크기 한도를 초과했습니다.')
            yield chunk

    staging_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='request-', dir=staging_root) as temp:
        parser = UploadParser(request.headers, stream(), Path(temp), max_bytes)
        try:
            form = await parser.parse()
            if not parser.complete:
                raise HTTPException(400, '업로드가 끝나기 전에 연결이 종료되었습니다.')
            yield form
        except MultiPartException:
            raise HTTPException(400, '업로드 형식이 올바르지 않습니다. docx·xlsx·pptx 파일(최대 4개)과 입력 항목을 확인하세요.') from None
        finally:
            # Includes unfinished parts absent from FormData and disconnects.
            for handle in parser._files_to_close_on_error:
                handle.close()
