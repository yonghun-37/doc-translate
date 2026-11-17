"""Keep upstream request/retry logic while enforcing TLS and proxy policy."""
import ssl

import httpx
from docutranslate.agents.segments_agent import SegmentsTranslateAgent


class SecureSegmentsAgent(SegmentsTranslateAgent):
    def __init__(self, config, *, ca_bundle: str | None, trust_env_proxy: bool):
        super().__init__(config)
        self.ssl_context = ssl.create_default_context(cafile=ca_bundle)
        self.trust_env_proxy = trust_env_proxy
        self.last_request_error = None

    async def _request_completion_async(self, client, data, headers):
        # Upstream 1.7.11 creates verify=False clients. Do not use those for I/O.
        # An explicit SSLContext also keeps CA verification independent of proxies.
        async with httpx.AsyncClient(verify=self.ssl_context, trust_env=self.trust_env_proxy,
                                     follow_redirects=False) as verified:
            try:
                return await super()._request_completion_async(verified, data, headers)
            except httpx.HTTPError as exc:
                self.last_request_error = exc
                raise

    def _request_completion_sync(self, client, data, headers):
        with httpx.Client(verify=self.ssl_context, trust_env=self.trust_env_proxy,
                          follow_redirects=False) as verified:
            try:
                return super()._request_completion_sync(verified, data, headers)
            except httpx.HTTPError as exc:
                self.last_request_error = exc
                raise
