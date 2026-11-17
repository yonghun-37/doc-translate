# 제3자 의존성 라이선스

`scripts/third-party-licenses.py`가 현재 Python 환경의 배포 메타데이터와 `frontend/node_modules`의 실제 설치 패키지에서 생성한 목록입니다. 네트워크를 사용하지 않습니다.

직접/개발/빌드 의존성은 프로젝트 선언을 기준으로 분류합니다. 그 외 설치 항목은 간접·환경 의존성이며, 설치 환경에 남아 있는 이전 패키지도 포함될 수 있습니다. 다른 운영체제용 미설치 선택 패키지는 이 목록에 포함되지 않으므로 배포 대상에서 다시 생성하세요. 잠금 파일 전체의 이름·버전은 `scripts/list-dependencies.sh`로 확인합니다.

`html2text`는 docutranslate의 선언만 있고 import되지 않아 uv override로 제외했습니다. 목록에 나타나면 설치 환경을 다시 동기화하세요. MPL-2.0의 docutranslate·certifi·lightningcss는 **수정 없이 사용**하며 확장은 앱의 래퍼·서브클래스로 구현합니다.

이 표는 설치된 라이선스 고지를 대신하지 않습니다. 패키지의 LICENSE·NOTICE와 번들 구성요소 고지를 함께 보관하세요. `확인 필요` 항목은 반입 전에 해당 파일을 확인해야 합니다.

## Python

| 패키지 | 버전 | 구분 | 라이선스 | 근거·비고 |
| --- | --- | --- | --- | --- |
| agent-detector | 2.0.0 | 간접·환경 | MIT | License-Expression |
| annotated-doc | 0.0.6 | 간접·환경 | MIT | License-Expression |
| annotated-types | 0.8.0 | 간접·환경 | MIT | License-Expression |
| anyio | 4.16.0 | 간접·환경 | MIT | License-Expression |
| babel | 2.18.0 | 간접·환경 | BSD-3-Clause | License |
| beautifulsoup4 | 4.15.0 | 간접·환경 | MIT License | License |
| certifi | 2026.10.23 | 간접·환경 | MPL-2.0 | License; 수정 없이 사용 |
| cffi | 2.1.1 | 간접·환경 | MIT-0 | License-Expression |
| charset-normalizer | 3.5.2 | 간접·환경 | MIT | License |
| click | 8.5.1 | 간접·환경 | BSD-3-Clause | License-Expression |
| cobble | 0.1.4 | 간접·환경 | BSD (메타데이터 분류) | Classifier |
| cryptography | 50.0.2 | 간접·환경 | Apache-2.0 OR BSD-3-Clause | License-Expression |
| daff | 1.4.2 | 직접 | MIT | License |
| detect-installer | 0.2.1 | 간접·환경 | 0BSD | License-Expression |
| dnspython | 2.9.2 | 간접·환경 | ISC | License-Expression |
| docutranslate | 1.7.11 | 직접 | MPL-2.0 | docutranslate-1.7.11.dist-info/licenses/LICENSE; 수정 없이 사용 |
| email-validator | 2.4.0 | 간접·환경 | Unlicense | License |
| et_xmlfile | 2.0.0 | 간접·환경 | MIT | License |
| fastapi | 0.163.1 | 직접 | MIT | License-Expression |
| fastapi-cli | 0.0.34 | 간접·환경 | MIT | License-Expression |
| fastapi-cloud-cli | 0.28.0 | 간접·환경 | MIT | License |
| fastar | 0.12.0 | 간접·환경 | MIT | License-Expression |
| googleapis-common-protos | 1.76.0 | 간접·환경 | Apache-2.0 | License-Expression |
| h11 | 0.16.0 | 간접·환경 | MIT | License |
| httpcore | 1.0.9 | 간접·환경 | BSD-3-Clause | License-Expression |
| httpcore2 | 2.16.2 | 간접·환경 | BSD-3-Clause | License-Expression |
| httptools | 0.9.0 | 간접·환경 | MIT | License-Expression |
| httpx | 0.28.1 | 개발 직접 | BSD-3-Clause | License |
| httpx2 | 2.16.2 | 간접·환경 | BSD-3-Clause | License-Expression |
| idna | 3.20 | 간접·환경 | BSD-3-Clause | License-Expression |
| iniconfig | 2.3.1 | 간접·환경 | MIT | License-Expression |
| Jinja2 | 3.1.6 | 간접·환경 | BSD-3-Clause | jinja2-3.1.6.dist-info/licenses/LICENSE.txt |
| json_repair | 0.64.9 | 간접·환경 | MIT | License-Expression |
| jsonpath-ng | 1.16.0 | 간접·환경 | Apache-2.0 | License-Expression |
| lxml | 6.1.3 | 직접 | BSD-3-Clause | License |
| mammoth | 1.13.0 | 간접·환경 | BSD-2-Clause | License |
| Markdown | 3.11.3 | 간접·환경 | BSD-3-Clause | License-Expression |
| markdown-it-py | 4.3.0 | 간접·환경 | MIT | markdown_it_py-4.3.0.dist-info/licenses/LICENSE |
| MarkupSafe | 3.0.4 | 간접·환경 | BSD-3-Clause | License-Expression |
| mdurl | 0.1.2 | 간접·환경 | MIT | mdurl-0.1.2.dist-info/LICENSE |
| msoffcrypto-tool | 6.1.0 | 간접·환경 | MIT | License |
| olefile | 0.47 | 간접·환경 | BSD | License |
| openpyxl | 3.1.5 | 직접 | MIT | License |
| opentelemetry-api | 1.45.2 | 간접·환경 | Apache-2.0 | License-Expression |
| opentelemetry-exporter-http-transport | 0.66b2 | 간접·환경 | Apache-2.0 | License-Expression |
| opentelemetry-exporter-otlp-common | 0.66b2 | 간접·환경 | Apache-2.0 | License-Expression |
| opentelemetry-exporter-otlp-proto-common | 1.45.2 | 간접·환경 | Apache-2.0 | License-Expression |
| opentelemetry-exporter-otlp-proto-http | 1.45.2 | 간접·환경 | Apache-2.0 | License-Expression |
| opentelemetry-proto | 1.45.2 | 간접·환경 | Apache-2.0 | License-Expression |
| opentelemetry-sdk | 1.45.2 | 간접·환경 | Apache-2.0 | License-Expression |
| opentelemetry-semantic-conventions | 0.66b2 | 간접·환경 | Apache-2.0 | License-Expression |
| packaging | 26.3 | 간접·환경 | Apache-2.0 OR BSD-2-Clause | License-Expression |
| pillow | 13.0.0 | 개발 직접 | MIT-CMU | License-Expression |
| platformdirs | 4.14.5 | 간접·환경 | MIT | License-Expression |
| pluggy | 1.7.0 | 간접·환경 | MIT | License |
| protobuf | 7.36.2 | 간접·환경 | 3-Clause BSD License | License |
| pycparser | 3.12 | 간접·환경 | BSD-3-Clause | License-Expression |
| pydantic | 2.14.3 | 간접·환경 | MIT | License-Expression |
| pydantic_core | 2.50.4 | 간접·환경 | MIT | License-Expression |
| pydantic-extra-types | 2.11.1 | 간접·환경 | MIT | License-Expression |
| pydantic-settings | 2.16.3 | 간접·환경 | MIT | License-Expression |
| Pygments | 2.21.0 | 간접·환경 | BSD-2-Clause | License-Expression |
| pymdown-extensions | 13.1 | 간접·환경 | MIT | License-Expression |
| pypdf | 7.1.0 | 간접·환경 | BSD-3-Clause | License-Expression |
| pysubs2 | 1.9.1 | 간접·환경 | MIT | License-Expression |
| pytest | 9.2.0 | 개발 직접 | MIT | License-Expression |
| python-docx | 1.2.0 | 직접 | MIT | License |
| python-dotenv | 1.2.4 | 간접·환경 | BSD-3-Clause | License |
| python-multipart | 0.0.34 | 간접·환경 | Apache-2.0 | License-Expression |
| python-pptx | 1.0.2 | 직접 | MIT | License |
| python-redlines | 2.0.0 | 직접 | MIT | License-Expression |
| python-redlines-docxodus | 2.0.0 | 간접·환경 | MIT | License-Expression |
| PyYAML | 6.0.3 | 간접·환경 | MIT | License |
| regex | 2026.11.15 | 간접·환경 | Apache-2.0 AND CNRI-Python | License-Expression |
| requests | 2.34.2 | 간접·환경 | Apache-2.0 | License |
| rich | 15.0.0 | 간접·환경 | MIT | License |
| rich-toolkit | 0.20.6 | 간접·환경 | MIT | License-Expression |
| rignore | 0.8.1 | 간접·환경 | MIT | License |
| sentry-sdk | 2.75.0 | 간접·환경 | MIT | License-Expression |
| shellingham | 1.5.4 | 간접·환경 | ISC License | License |
| six | 1.17.0 | 간접·환경 | MIT | License |
| soupsieve | 4.1.1 | 간접·환경 | MIT | License-Expression |
| srt | 3.5.3 | 간접·환경 | MIT | License |
| starlette | 1.10.0 | 간접·환경 | BSD-3-Clause | License-Expression |
| truststore | 0.10.5 | 간접·환경 | MIT | License-Expression |
| typer | 0.29.1 | 간접·환경 | MIT | License-Expression |
| typing_extensions | 4.16.0 | 간접·환경 | PSF-2.0 | License-Expression |
| typing-inspection | 0.4.5 | 간접·환경 | MIT | License-Expression |
| urllib3 | 2.8.0 | 간접·환경 | MIT | License-Expression |
| uvicorn | 0.54.0 | 직접 | BSD-3-Clause | License-Expression |
| uvloop | 0.23.0 | 간접·환경 | MIT License | License |
| watchfiles | 1.3.0 | 간접·환경 | MIT | License |
| websockets | 17.4 | 간접·환경 | BSD-3-Clause | License-Expression |
| xlsx2html | 0.6.4 | 간접·환경 | MIT | License |
| xlsxwriter | 3.3.1 | 간접·환경 | BSD-2-Clause | License-Expression |

## npm

| 패키지 | 버전 | 구분 | 라이선스 | 근거·비고 |
| --- | --- | --- | --- | --- |
| @adobe/css-tools | 4.5.0 | 간접 | MIT | package.json |
| @asamuzakjp/css-color | 7.1.9 | 간접 | MIT | package.json |
| @asamuzakjp/dom-selector | 10.0.5 | 간접 | MIT | package.json |
| @babel/code-frame | 7.29.7 | 간접 | MIT | package.json |
| @babel/helper-validator-identifier | 7.29.7 | 간접 | MIT | package.json |
| @babel/runtime | 7.29.10 | 간접 | MIT | package.json |
| @bramus/specificity | 2.4.3 | 간접 | MIT | package.json |
| @csstools/color-helpers | 6.1.2 | 간접 | MIT-0 | package.json |
| @csstools/css-calc | 3.4.3 | 간접 | MIT | package.json |
| @csstools/css-color-parser | 4.2.7 | 간접 | MIT | package.json |
| @csstools/css-parser-algorithms | 4.0.2 | 간접 | MIT | package.json |
| @csstools/css-syntax-patches-for-csstree | 1.1.16 | 간접 | MIT-0 | package.json |
| @csstools/css-tokenizer | 4.0.2 | 간접 | MIT | package.json |
| @exodus/bytes | 1.16.0 | 간접 | MIT | package.json |
| @jridgewell/resolve-uri | 3.1.2 | 간접 | MIT | package.json |
| @jridgewell/sourcemap-codec | 1.6.0 | 간접 | MIT | package.json |
| @jridgewell/trace-mapping | 0.3.31 | 간접 | MIT | package.json |
| @oxc-project/types | 0.156.0 | 간접 | MIT | package.json |
| @rolldown/binding-linux-x64-gnu | 1.2.16 | 간접 | MIT | package.json |
| @rolldown/pluginutils | 1.0.1 | 간접 | MIT | package.json |
| @tanstack/query-core | 5.105.3 | 간접 | MIT | package.json |
| @tanstack/react-query | 5.105.3 | 직접 | MIT | package.json |
| @testing-library/dom | 10.4.2 | 간접 | MIT | package.json |
| @testing-library/jest-dom | 7.0.1 | 개발 직접 | MIT | package.json |
| @testing-library/react | 16.3.3 | 개발 직접 | MIT | package.json |
| @testing-library/user-event | 14.6.8 | 개발 직접 | MIT | package.json |
| @types/aria-query | 5.0.4 | 간접 | MIT | package.json |
| @types/chai | 5.2.3 | 간접 | MIT | package.json |
| @types/deep-eql | 4.0.2 | 간접 | MIT | package.json |
| @types/estree | 1.0.10 | 간접 | MIT | package.json |
| @types/react | 19.3.0 | 개발 직접 | MIT | package.json |
| @types/react-dom | 19.3.0 | 개발 직접 | MIT | package.json |
| @vitejs/plugin-react | 6.2.1 | 개발 직접 | MIT | package.json |
| @vitest/mocker | 5.1.0 | 간접 | MIT | package.json |
| @vitest/spy | 5.1.0 | 간접 | MIT | package.json |
| ansi-regex | 5.0.1 | 간접 | MIT | package.json |
| ansi-styles | 5.2.0 | 간접 | MIT | package.json |
| aria-query | 5.3.0 | 간접 | Apache-2.0 | package.json |
| assertion-error | 2.0.1 | 간접 | MIT | package.json |
| bidi-js | 1.1.0 | 간접 | MIT | package.json |
| chai | 6.3.0 | 간접 | MIT | package.json |
| cookie | 1.1.1 | 간접 | MIT | package.json |
| css-tree | 3.2.1 | 간접 | MIT | package.json |
| css.escape | 1.5.1 | 간접 | MIT | package.json |
| csstype | 3.2.3 | 간접 | MIT | package.json |
| data-urls | 8.0.0 | 간접 | MIT | package.json |
| decimal.js | 10.6.0 | 간접 | MIT | package.json |
| dequal | 2.0.3 | 간접 | MIT | package.json |
| detect-libc | 2.1.2 | 간접 | Apache-2.0 | package.json |
| dom-accessibility-api | 0.5.16 | 간접 | MIT | package.json |
| dom-accessibility-api | 0.6.3 | 간접 | MIT | package.json |
| entities | 9.0.0 | 간접 | BSD-2-Clause | package.json |
| es-module-lexer | 2.3.2 | 간접 | MIT | package.json |
| estree-walker | 3.0.3 | 간접 | MIT | package.json |
| expect-type | 1.4.0 | 간접 | Apache-2.0 | package.json |
| fdir | 6.5.0 | 간접 | MIT | package.json |
| html-encoding-sniffer | 7.0.0 | 간접 | MIT | package.json |
| indent-string | 4.0.0 | 간접 | MIT | package.json |
| is-potential-custom-element-name | 1.0.1 | 간접 | MIT | package.json |
| js-tokens | 4.0.0 | 간접 | MIT | package.json |
| jsdom | 30.1.3 | 개발 직접 | MIT | package.json |
| lightningcss | 1.33.0 | 간접 | MPL-2.0 | package.json; 수정 없이 사용 |
| lightningcss-linux-x64-gnu | 1.33.0 | 간접 | MPL-2.0 | package.json; 수정 없이 사용 |
| lru-cache | 11.5.3 | 간접 | BlueOak-1.0.0 | package.json |
| lz-string | 1.5.0 | 간접 | MIT | package.json |
| magic-string | 1.4.5 | 간접 | MIT | package.json |
| mdn-data | 2.27.1 | 간접 | CC0-1.0 | package.json |
| min-indent | 1.0.1 | 간접 | MIT | package.json |
| nanoid | 3.3.20 | 간접 | MIT | package.json |
| obug | 3.0.0 | 간접 | MIT | package.json |
| parse5 | 8.1.0 | 간접 | MIT | package.json |
| picocolors | 1.1.1 | 간접 | ISC | package.json |
| picomatch | 4.0.7 | 간접 | MIT | package.json |
| postcss | 8.5.32 | 간접 | MIT | package.json |
| pretty-format | 27.5.1 | 간접 | MIT | package.json |
| punycode | 2.3.1 | 간접 | MIT | package.json |
| react | 19.3.1 | 직접 | MIT | package.json |
| react-dom | 19.3.1 | 직접 | MIT | package.json |
| react-is | 17.0.2 | 간접 | MIT | package.json |
| react-router | 7.18.5 | 간접 | MIT | package.json |
| react-router-dom | 7.18.5 | 직접 | MIT | package.json |
| redent | 3.0.0 | 간접 | MIT | package.json |
| require-from-string | 2.0.2 | 간접 | MIT | package.json |
| rolldown | 1.2.16 | 간접 | MIT | package.json |
| saxes | 6.0.0 | 간접 | ISC | package.json |
| scheduler | 0.28.0 | 간접 | MIT | package.json |
| set-cookie-parser | 2.7.3 | 간접 | MIT | package.json |
| source-map-js | 1.2.2 | 간접 | BSD-3-Clause | package.json |
| std-env | 4.3.0 | 간접 | MIT | package.json |
| strip-indent | 3.0.0 | 간접 | MIT | package.json |
| tinybench | 6.2.3 | 간접 | MIT | package.json |
| tinyexec | 1.3.1 | 간접 | MIT | package.json |
| tinyglobby | 0.2.17 | 간접 | MIT | package.json |
| tldts | 7.4.19 | 간접 | MIT | package.json |
| tldts-core | 7.4.19 | 간접 | MIT | package.json |
| tough-cookie | 6.0.2 | 간접 | BSD-3-Clause | package.json |
| tr46 | 7.0.0 | 간접 | MIT | package.json |
| typescript | 5.9.3 | 개발 직접 | Apache-2.0 | package.json |
| undici | 8.12.3 | 간접 | MIT | package.json |
| vite | 8.3.5 | 개발 직접 | MIT | package.json |
| vitest | 5.1.0 | 개발 직접 | MIT | package.json |
| w3c-xmlserializer | 6.0.0 | 간접 | MIT | package.json |
| webidl-conversions | 8.0.1 | 간접 | BSD-2-Clause | package.json |
| whatwg-mimetype | 5.0.0 | 간접 | MIT | package.json |
| whatwg-url | 17.3.0 | 간접 | MIT | package.json |
| why-is-node-running | 3.2.1 | 간접 | MIT | package.json |
| xml-name-validator | 5.0.0 | 간접 | Apache-2.0 | package.json |
| xmlchars | 2.2.0 | 간접 | MIT | package.json |
