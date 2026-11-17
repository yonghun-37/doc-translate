import argparse
import os
from pathlib import Path
import sys
import time

import uvicorn

from app.config import Config, ConfigError, LANGUAGES
from app.pipeline import Pipeline, StateError
from app.diagnostics import safe_error
from app.reuse_agent import ReuseAgent
from app.web import create_app


def parser():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument('--root',default=argparse.SUPPRESS,help='작업 루트 (기본: DOC_TRANSLATE_ROOT 또는 현재 디렉토리)')
    common.add_argument('--config',default=argparse.SUPPRESS,help='TOML 설정 경로 (기본: <root>/config.toml)')
    p = argparse.ArgumentParser(prog='doc-translate',description='Office 개정본 검토 및 중국어 번역',parents=[common])
    sub = p.add_subparsers(dest='command',required=True)
    for name in ('check-translator',):
        sub.add_parser(name,parents=[common])
    serve = sub.add_parser('serve',parents=[common])
    serve.add_argument('--host',default='127.0.0.1')
    serve.add_argument('--port',type=int,default=8000)
    serve.add_argument('--max-upload-mb',type=int,default=50,help='업로드 파일 크기 한도 MB (기본: 50)')
    serve.add_argument('--allowed-host',action='append',default=[],metavar='HOST',
                       help='인증된 리버스 프록시(예: tailscale serve)가 전달하는 Host 이름. 바인딩은 127.0.0.1 유지')
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    root = Path(getattr(args,'root',os.environ.get('DOC_TRANSLATE_ROOT','.'))).resolve()
    try:
        config = Config.load(root, getattr(args, 'config', None))
        if args.command=='check-translator':
            config.validate()
            # Actual requests happen only when this command is explicitly run.
            print(f'json_mode={str(config.json_mode).lower()} (JSON 배열 응답 계약; json_object 지원만으로 활성화하지 마세요.)')
            for lang in LANGUAGES:
                agent = config.make_agent(lang)
                started = time.perf_counter()
                result = ReuseAgent({},agent).send_segments(['문서 번역 연결 테스트입니다.'],3000)
                elapsed = time.perf_counter() - started
                stats = agent.get_full_stats() if hasattr(agent, 'get_full_stats') else {}
                reasoning = stats.get('reasoning_tokens')
                reasoning = reasoning if type(reasoning) is int else '미제공'
                print(f'{lang}: {result[0]}')
                print(f'소요 시간: {elapsed:.2f}초 · 추론 토큰: {reasoning}')
            return 0
        if args.command=='serve':
            if args.host!='127.0.0.1':
                raise StateError('로그인 없는 검토 화면은 127.0.0.1에만 바인딩할 수 있습니다.')
            if any(not h or '*' in h or '/' in h for h in args.allowed_host):
                raise StateError('--allowed-host에는 와일드카드·URL 없는 호스트 이름만 넣을 수 있습니다.')
            if args.max_upload_mb <= 0:
                raise StateError('업로드 크기 한도는 0보다 커야 합니다.')
            uvicorn.run(create_app(root, pipeline=Pipeline(root, config=config), extra_hosts=args.allowed_host,
                                   max_upload_mb=args.max_upload_mb),
                        host=args.host,port=args.port)
            return 0
    except KeyboardInterrupt:
        return 0
    except (ConfigError,StateError) as exc:
        print(str(exc),file=sys.stderr)
        return 1
    except FileNotFoundError:
        print('문서 또는 필요한 파일을 찾을 수 없습니다.',file=sys.stderr)
        return 1
    except Exception as exc:
        code, message = safe_error(exc)
        print(f'작업 실패 — {code}: {message}',file=sys.stderr)
        return 1


if __name__=='__main__':
    sys.exit(main())
