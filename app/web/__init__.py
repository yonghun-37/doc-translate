"""Local job JSON API and the built React application."""
from pathlib import Path
import re
from urllib.parse import quote, urlsplit

from fastapi import BackgroundTasks, Body, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.pipeline import InvalidUpload, Pipeline, StateError
from app.storage import read_json
from app import grid
from app.web.models import Decision, Rejection, JobDetail, JobSummary, SheetDiff, SlideDiff
from app.web.uploads import upload_form


def create_app(root: Path, *, pipeline: Pipeline | None = None, dist_dir: Path | None = None,
               extra_hosts: list[str] | tuple[str, ...] = (), max_upload_mb: int = 50):
    if max_upload_mb <= 0:
        raise ValueError('업로드 크기 한도는 0보다 커야 합니다.')
    pipeline = pipeline or Pipeline(root)
    store = pipeline.store
    dist = Path(dist_dir) if dist_dir is not None else Path(__file__).resolve().parents[2] / 'frontend/dist'
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.state.pipeline = pipeline
    app.state.max_upload_bytes = max_upload_mb * 1024 * 1024
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1', 'localhost', '[::1]', *extra_hosts])

    @app.exception_handler(FileNotFoundError)
    async def missing_job_file(request: Request, exc: FileNotFoundError):
        # A concurrent job deletion can remove artifacts after a status read.
        return JSONResponse({'detail': '작업 또는 파일을 찾을 수 없습니다.'}, status_code=404)

    @app.middleware('http')
    async def local_requests(request: Request, call_next):
        denied = False
        if request.method not in {'GET', 'HEAD', 'OPTIONS'}:
            origin = request.headers.get('origin')
            try:
                parsed = urlsplit(origin) if origin else None
                denied = request.headers.get('sec-fetch-site') == 'cross-site' or bool(
                    parsed and (parsed.scheme != request.url.scheme or parsed.netloc != request.url.netloc))
            except ValueError:
                denied = True
        response = (JSONResponse({'detail': '다른 사이트에서 보낸 요청은 허용하지 않습니다.'}, status_code=403)
                    if denied else await call_next(request))
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; frame-ancestors 'self'; form-action 'self'; base-uri 'none'"
        return response

    def state_for(job_id):
        try:
            return store.read_status(job_id)
        except (FileNotFoundError, ValueError):
            raise HTTPException(404, '작업을 찾을 수 없습니다.') from None

    def file_url(job_id, name):
        return f'/api/jobs/{job_id}/files/' + quote(name, safe='')

    def detail(state):
        folder = store.job_dir(state['id']) / 'review'
        artifacts = {}
        if (folder / 'redline.docx').is_file():
            artifacts['redline'] = file_url(state['id'], 'redline.docx')
        outputs = [{'lang': lang, 'url': file_url(state['id'], Path(path).name)}
                   for lang, path in state['outputs'].items()] if state['status'] == 'translated' else []
        return {**state, 'changes': read_json(folder / 'changes.json'),
                'alignment': read_json(folder / 'alignment.json'), 'plan': read_json(folder / 'plan.json'),
                'artifacts': artifacts, 'outputs': outputs}

    @app.get('/api/jobs', response_model=list[JobSummary])
    def jobs():
        return store.statuses()

    @app.post('/api/jobs', status_code=201, response_model=JobDetail, response_model_exclude_unset=True)
    async def uploads(request: Request, background_tasks: BackgroundTasks):
        async with upload_form(request, store.path('logs', '.uploads'), app.state.max_upload_bytes) as form:
            roles = {'original': 'original', 'revised': 'revised', 'base_zh_cn': 'base_zh-CN', 'base_zh_tw': 'base_zh-TW'}
            if (len(form.multi_items()) != len(form) or set(form) - {*roles, 'title', 'by'}
                    or not isinstance(form.get('revised'), UploadFile)
                    or any(not isinstance(form[key], UploadFile) for key in roles if key in form)
                    or any(not isinstance(form.get(key, ''), str) for key in ('title', 'by'))):
                raise HTTPException(400, '수정본과 선택 파일·제목·올린 사람 항목을 확인하세요.')
            if len(form.get('title', '')) > 240 or len(form.get('by', '')) > 200:
                raise HTTPException(400, '제목은 240자, 이름은 200자 이내로 입력하세요.')
            files = {role: (Path(form[key].file.name), form[key].filename) for key, role in roles.items() if key in form}
            try:
                state = await run_in_threadpool(pipeline.upload, files, title=form.get('title'), by=form.get('by'))
            except InvalidUpload as exc:
                raise HTTPException(400, str(exc)) from None
            if state.get('preview', {}).get('status') == 'pending':
                background_tasks.add_task(pipeline.prepare_preview, state['id'])
            return detail(state)

    @app.get('/api/jobs/{job_id}', response_model=JobDetail, response_model_exclude_unset=True)
    def job_detail(job_id: str):
        return detail(state_for(job_id))

    @app.get('/api/jobs/{job_id}/sheets', response_model=list[SheetDiff])
    def sheets(job_id: str):
        state = state_for(job_id)
        if state['ext'] != 'xlsx':
            raise HTTPException(404, '엑셀 문서에서만 시트 비교를 제공합니다.')
        if 'original' not in state['files']:
            return []
        return read_json(store.job_dir(job_id) / 'review' / 'sheets.json')

    @app.get('/api/jobs/{job_id}/grid')
    def sheet_grid(job_id: str, sheet: str | None = None,
                   row: int | None = Query(default=None, ge=1, le=1048576),
                   col: int | None = Query(default=None, ge=1, le=16384)):
        state = state_for(job_id)
        if state['ext'] != 'xlsx':
            raise HTTPException(404, '엑셀 문서에서만 격자를 제공합니다.')
        if 'original' not in state['files']:
            return []
        folder = store.job_dir(job_id)
        return grid.build(safe_file(folder, 'inputs/original.xlsx'), safe_file(folder, 'inputs/revised.xlsx'),
                          read_json(folder / 'review/sheets.json'), read_json(folder / 'review/changes.json'),
                          sheet=sheet, row=row, col=col)

    @app.get('/api/jobs/{job_id}/slides', response_model=list[SlideDiff])
    def slides(job_id: str):
        state = state_for(job_id)
        if state['ext'] != 'pptx':
            raise HTTPException(404, '파워포인트 문서에서만 슬라이드 비교를 제공합니다.')
        path = store.job_dir(job_id) / 'review' / 'slides.json'
        groups = {}
        for change in read_json(path) if path.exists() else []:
            groups.setdefault(change['slide'], []).append(change)
        return [{'slide': slide, 'items': items} for slide, items in sorted(groups.items())]

    def action(operation, job_id, **kwargs):
        state_for(job_id)
        try:
            return operation(job_id, **kwargs)
        except FileNotFoundError:
            raise HTTPException(404, '작업을 찾을 수 없습니다.') from None
        except StateError as exc:
            raise HTTPException(409, str(exc)) from None

    def scheduled(state, background_tasks):
        background_tasks.add_task(pipeline.translate, state['id'])
        return detail(state)

    @app.post('/api/jobs/{job_id}/translate', status_code=202, response_model=JobDetail, response_model_exclude_unset=True)
    def translate(job_id: str, background_tasks: BackgroundTasks, body: Decision | None = Body(default=None)):
        state = action(pipeline.start_translation, job_id, by=body.by if body else None, background=True)
        return scheduled(state, background_tasks)

    @app.post('/api/jobs/{job_id}/reject', response_model=JobDetail, response_model_exclude_unset=True)
    def reject(job_id: str, body: Rejection | None = Body(default=None)):
        if not body or not body.reason.strip():
            raise HTTPException(400, '반려 사유를 입력하세요.')
        return detail(action(pipeline.reject, job_id, reason=body.reason, by=body.by))

    @app.post('/api/jobs/{job_id}/retry', status_code=202, response_model=JobDetail, response_model_exclude_unset=True)
    def retry(job_id: str, background_tasks: BackgroundTasks):
        return scheduled(action(pipeline.retry, job_id, background=True), background_tasks)

    @app.delete('/api/jobs/{job_id}', status_code=204)
    def delete(job_id: str):
        action(pipeline.delete, job_id)
        return Response(status_code=204)

    @app.get('/api/jobs/{job_id}/files/{name:path}')
    def files(job_id: str, name: str):
        state = state_for(job_id)
        if name.startswith('preview/'):
            leaf = name.removeprefix('preview/')
            if (state.get('preview', {}).get('status') != 'ready'
                    or not re.fullmatch(r'(?:redline|original|revised)-[0-9]{3,}\.png|overlays\.json', leaf)):
                raise HTTPException(404)
            return FileResponse(safe_file(store.job_dir(job_id), f'review/preview/{leaf}'))
        if '/' in name or '\\' in name:
            raise HTTPException(404)
        folder = store.job_dir(job_id)
        if name == 'redline.docx':
            candidate = safe_file(folder, f'review/{name}')
        else:
            path = f'output/{name}'
            if state['status'] != 'translated' or path not in state['outputs'].values():
                raise HTTPException(404)
            candidate = safe_file(folder, path)
        return FileResponse(candidate, filename=candidate.name)

    @app.get('/assets/{file_path:path}')
    def assets(file_path: str):
        return FileResponse(safe_file(dist / 'assets', file_path))

    @app.get('/{path:path}')
    def spa(path: str):
        if path == 'api' or path.startswith('api/') or path == 'assets':
            raise HTTPException(404)
        if not (dist / 'index.html').is_file():
            return PlainTextResponse('프론트엔드를 빌드하세요: cd frontend && npm run build')
        return FileResponse(dist / 'index.html', media_type='text/html')

    return app


def safe_file(base: Path, file_path: str) -> Path:
    candidate = base / file_path
    if (not candidate.resolve().is_relative_to(base.resolve()) or not candidate.is_file()
            or any(p.is_symlink() for p in [candidate, *candidate.parents])):
        raise HTTPException(404)
    return candidate
