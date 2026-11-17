#!/usr/bin/env bash
# 잠금 파일에서 사내 미러 점검용 이름·버전을 출력합니다. 네트워크 사용 없음.
set -euo pipefail
project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
python_bin="${PYTHON:-$project_root/.venv/bin/python}"
"$python_bin" - "$project_root" <<'PY'
import json
from pathlib import Path
import sys
import tomllib

root = Path(sys.argv[1])
print('생태계\t패키지\t버전')
lock = root / 'uv.lock'
if lock.exists():
    packages = tomllib.loads(lock.read_text())['package']
    for name, version in sorted({(p['name'], p.get('version', '')) for p in packages if p['name'] != 'doc-translate'}):
        print(f'python\t{name}\t{version}')
else:
    print('주의: uv.lock이 없어 Python 잠금 목록을 출력할 수 없습니다. 사내 미러에서 uv lock 후 다시 실행하세요.', file=sys.stderr)
packages = json.loads((root / 'frontend/package-lock.json').read_text())['packages']
for name, version in sorted({(p.get('name') or path.rsplit('node_modules/', 1)[-1], p['version']) for path, p in packages.items() if path and 'version' in p}):
    print(f'npm\t{name}\t{version}')
if not lock.exists():
    sys.exit(1)
PY
