#!/usr/bin/env python3
"""Generate an offline inventory from installed Python/npm metadata."""
import argparse
from importlib import metadata
import json
from pathlib import Path
import re
import tomllib

ROOT = Path(__file__).resolve().parents[1]
MPL = {'docutranslate', 'certifi', 'lightningcss'}
CLASSIFIERS = {
    'MIT License': 'MIT', 'BSD License': 'BSD (메타데이터 분류)',
    'Apache Software License': 'Apache-2.0',
    'Mozilla Public License 2.0 (MPL 2.0)': 'MPL-2.0',
    'Python Software Foundation License': 'PSF-2.0',
    'ISC License (ISCL)': 'ISC',
}


def normalize(name):
    return re.sub(r'[-_.]+', '-', name).lower()


def dependency_name(requirement):
    return normalize(re.match(r'[A-Za-z0-9_.-]+', requirement).group())


def license_text(text):
    spdx = re.search(r'SPDX-License-Identifier:\s*([^\r\n]+)', text)
    if spdx:
        return spdx[1].strip()
    if 'Mozilla Public License' in text and ('2.0' in text or 'Version 2' in text):
        return 'MPL-2.0'
    if 'Permission is hereby granted, free of charge' in text:
        return 'MIT'
    if 'Apache License' in text and '2.0' in text:
        return 'Apache-2.0'
    if 'Redistribution and use in source and binary forms' in text:
        return 'BSD-3-Clause' if 'Neither the name' in text or 'Neither the names' in text else 'BSD (라이선스 파일 확인)'
    if 'ISC License' in text or ('Permission to use, copy, modify, and/or distribute' in text and 'THE SOFTWARE IS PROVIDED' in text):
        return 'ISC'
    return None


def python_license(dist):
    meta = dist.metadata
    if value := meta.get('License-Expression'):
        return value.strip(), 'License-Expression'
    value = (meta.get('License') or '').strip()
    if value and value not in {'UNKNOWN', 'Unknown'} and len(value) < 120 and '\n' not in value:
        return value, 'License'
    # Metadata may contain the entire license; otherwise inspect packaged notices.
    files = [f for f in dist.files or [] if re.search(r'(^|/)(license|copying)(\.|/|$)', str(f), re.I)]
    for file in files:
        path = Path(dist.locate_file(file))
        if path.is_file():
            text = path.read_text(encoding='utf-8', errors='replace')
            if detected := license_text(text):
                return detected, str(file)
    for classifier in meta.get_all('Classifier', []):
        tail = classifier.rsplit(' :: ', 1)[-1]
        if tail in CLASSIFIERS:
            return CLASSIFIERS[tail], 'Classifier'
    if detected := license_text(value):
        return detected, 'License 본문'
    return '확인 필요', '설치 메타데이터에 라이선스 식별자 없음'


def npm_packages(node_modules):
    if not node_modules.exists():
        return
    for entry in sorted(node_modules.iterdir()):
        if entry.name.startswith('.') or not entry.is_dir():
            continue
        packages = sorted(entry.iterdir()) if entry.name.startswith('@') else [entry]
        for package in packages:
            path = package / 'package.json'
            if not path.is_file():
                continue
            data = json.loads(path.read_text())
            yield package, data
            yield from npm_packages(package / 'node_modules')


def npm_license(path, data):
    value = data.get('license') or data.get('licenses')
    if isinstance(value, dict):
        value = value.get('type')
    if isinstance(value, list):
        value = ' OR '.join(v.get('type', '') if isinstance(v, dict) else str(v) for v in value)
    if value:
        return str(value), 'package.json'
    for file in sorted(path.iterdir()):
        if file.is_file() and file.name.lower().startswith(('license', 'copying')):
            if detected := license_text(file.read_text(encoding='utf-8', errors='replace')):
                return detected, file.name
    return '확인 필요', '설치 메타데이터에 라이선스 식별자 없음'


def cell(value):
    return str(value).replace('|', '\\|').replace('\n', ' ').replace('\r', '')


def generate(root=ROOT):
    project = tomllib.loads((root / 'pyproject.toml').read_text())
    direct = {dependency_name(d) for d in project['project']['dependencies']}
    dev = {dependency_name(d) for group in project.get('dependency-groups', {}).values() for d in group if isinstance(d, str)}
    build = {dependency_name(d) for d in project['build-system']['requires']}
    lines = ['# 제3자 의존성 라이선스', '',
        '`scripts/third-party-licenses.py`가 현재 Python 환경의 배포 메타데이터와 `frontend/node_modules`의 실제 설치 패키지에서 생성한 목록입니다. 네트워크를 사용하지 않습니다.', '',
        '직접/개발/빌드 의존성은 프로젝트 선언을 기준으로 분류합니다. 그 외 설치 항목은 간접·환경 의존성이며, 설치 환경에 남아 있는 이전 패키지도 포함될 수 있습니다. 다른 운영체제용 미설치 선택 패키지는 이 목록에 포함되지 않으므로 배포 대상에서 다시 생성하세요. 잠금 파일 전체의 이름·버전은 `scripts/list-dependencies.sh`로 확인합니다.', '',
        '`html2text`는 docutranslate의 선언만 있고 import되지 않아 uv override로 제외했습니다. 목록에 나타나면 설치 환경을 다시 동기화하세요. MPL-2.0의 docutranslate·certifi·lightningcss는 **수정 없이 사용**하며 확장은 앱의 래퍼·서브클래스로 구현합니다.', '',
        '이 표는 설치된 라이선스 고지를 대신하지 않습니다. 패키지의 LICENSE·NOTICE와 번들 구성요소 고지를 함께 보관하세요. `확인 필요` 항목은 반입 전에 해당 파일을 확인해야 합니다.', '',
        '미리보기는 pypdfium2 5.15.2(BSD-3-Clause·Apache-2.0 및 PDFium 번들 고지)를 사용합니다. LibreOffice(MPL-2.0)는 서버에 별도 설치하는 외부 실행 프로그램이며 저장소·Python 패키지에 포함하지 않습니다. `[render]`로 실행 경로·제한을 설정합니다. 번역 진행의 `progress_batch`는 기존 docutranslate 호출을 묶는 앱 설정이며 추가 의존성이 없습니다.', '',
        '## Python', '', '| 패키지 | 버전 | 구분 | 라이선스 | 근거·비고 |', '| --- | --- | --- | --- | --- |']
    for dist in sorted(metadata.distributions(), key=lambda d: normalize(d.metadata['Name'])):
        name = dist.metadata['Name']
        norm = normalize(name)
        if norm == 'doc-translate':
            continue
        lic, evidence = python_license(dist)
        kind = '직접' if norm in direct else '개발 직접' if norm in dev else '빌드 직접' if norm in build else '간접·환경'
        if norm in MPL:
            evidence += '; 수정 없이 사용'
        lines.append('| ' + ' | '.join(map(cell, [name, dist.version, kind, lic, evidence])) + ' |')
    frontend = json.loads((root / 'frontend/package.json').read_text())
    lines += ['', '## npm', '', '| 패키지 | 버전 | 구분 | 라이선스 | 근거·비고 |', '| --- | --- | --- | --- | --- |']
    packages = {}
    for path, data in npm_packages(root / 'frontend/node_modules'):
        if data.get('name') and data.get('version'):
            packages[(data['name'], data['version'])] = (path, data)
    for (name, version), (path, data) in sorted(packages.items()):
        lic, evidence = npm_license(path, data)
        kind = '직접' if name in frontend.get('dependencies', {}) else '개발 직접' if name in frontend.get('devDependencies', {}) else '간접'
        if name in MPL or name.startswith('lightningcss-'):
            evidence += '; 수정 없이 사용'
        lines.append('| ' + ' | '.join(map(cell, [name, version, kind, lic, evidence])) + ' |')
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='설치된 의존성 라이선스 목록을 오프라인으로 생성합니다.')
    parser.add_argument('--output', type=Path, default=ROOT / 'THIRD_PARTY_LICENSES.md')
    args = parser.parse_args()
    args.output.write_text(generate(), encoding='utf-8')
    print(f'라이선스 목록 생성: {args.output}')
