"""Diagnostics with no prompt, response body, URL, path or secret payloads."""
import errno
import logging
from pathlib import Path

import httpx

from app.storage import now

# Only application-authored messages known to contain no document data survive.
_SAFE_MESSAGES = {
    '번역 결과의 개수 또는 내용이 올바르지 않습니다.',
    '번역 엔진에서 일부 세그먼트 처리에 실패했습니다.',
    '지정한 환경변수에서 API 키를 찾을 수 없습니다.',
    '키 파일을 읽을 수 없습니다. 환경변수 또는 키 파일을 확인하세요.',
    '키 파일에 유효한 키가 없습니다.',
    '키 파일은 저장소 밖에 있어야 합니다.',
    '원격 전송이 차단되었습니다. allowed_hosts 설정을 확인하세요.',
    'ca_bundle 인증서 파일을 찾을 수 없습니다.',
    '인증서 또는 번역기 설정을 확인하세요.',
}


def safe_error(exc: BaseException) -> tuple[str, str]:
    # Preserve the real network cause when upstream falls back to source text.
    cause = exc
    seen = set()
    while cause.__cause__ is not None and id(cause) not in seen and not isinstance(cause, httpx.HTTPError):
        seen.add(id(cause))
        cause = cause.__cause__
    code = type(cause).__name__
    if isinstance(cause, httpx.HTTPStatusError):
        status = cause.response.status_code
        label = {400: '요청 형식 또는 모델 설정 오류', 401: 'API 키 인증 실패',
                 403: '접근 권한 거부', 404: 'API 경로 또는 모델을 찾을 수 없음',
                 429: '요청 한도 초과'}.get(status, 'LLM 서버 응답 오류')
        return code, f'HTTP {status}: {label}'
    if isinstance(cause, httpx.TimeoutException):
        return code, 'LLM 응답 시간 제한을 초과했습니다.'
    if isinstance(cause, httpx.ConnectError):
        return code, 'LLM 연결에 실패했습니다. 주소·인증서·프록시를 확인하세요.'
    if isinstance(cause, httpx.RequestError):
        return code, 'LLM 요청을 전송하거나 응답을 읽지 못했습니다.'
    if isinstance(cause, OSError):
        return code, f'파일 또는 시스템 작업 실패 ({errno.errorcode.get(cause.errno, "IO_ERROR")})'
    if isinstance(cause, KeyboardInterrupt):
        return code, '사용자가 작업을 중단했습니다.'
    message = str(cause)
    if message in _SAFE_MESSAGES:
        return code, message
    return code, '처리에 실패했습니다. 민감정보가 포함될 수 있어 예외 상세는 생략했습니다.'


class LibraryLogHandler(logging.Handler):
    def __init__(self, root: Path):
        super().__init__(logging.WARNING)
        self.path = root / 'logs/library.log'

    def emit(self, record):
        # Never format record.msg/args/exception: upstream includes document text.
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open('a', encoding='utf-8') as handle:
            handle.write(f'{now()} {record.levelname} docutranslate: 라이브러리 경고/오류 발생 (원문 보호를 위해 메시지 생략)\n')


def library_logger(root: Path) -> logging.Logger:
    logger = logging.Logger('doc-translate.library', level=logging.WARNING)
    logger.propagate = False
    logger.addHandler(LibraryLogHandler(root))
    return logger
