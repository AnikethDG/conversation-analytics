"""Sentinel — Enterprise Customer 360 & Risk Advisor_v2 (Vertex AI Agent Engine).

Exports `root_agent` for `adk deploy agent_engine` using `CloudRunOIDCMcpToolset`,
which overrides `_build_headers` + `header_provider` so every MCP HTTP request
(`initialize`, `tools/list`, `tools/call`) carries a fresh Google-signed OIDC ID
token—even when `readonly_context` is None or `mtls_transport` is enabled.
"""

import json
import logging
import os
from pathlib import Path
import time
from typing import Dict, Tuple
import urllib.parse
import urllib.request

from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams
import google.auth
from google.auth.transport.requests import Request
from google.oauth2 import id_token

logger = logging.getLogger("sentinel_advisor_v2")

PROMPT_FILE = Path(__file__).with_name("prompt_v2.md")
_TOKEN_CACHE: Dict[str, Tuple[str, float]] = {}
_TOKEN_TTL_SECONDS = 2700.0  # Refresh every 45 mins (OIDC tokens valid 60 mins)


def _is_valid_jwt(val: object) -> bool:
    return isinstance(val, str) and len(val.strip()) > 40 and val.count(".") == 2


def _fetch_oidc_bearer_token(audience_url: str) -> str:
    """Fetches and caches a Google-signed OIDC ID token for Cloud Run IAM auth."""
    now = time.monotonic()
    cached = _TOKEN_CACHE.get(audience_url)
    if cached and now < cached[1]:
        return cached[0]

    req = Request()
    creds, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    creds.refresh(req)

    # 1. Local developer user OAuth ADC provides creds.id_token directly
    tok = getattr(creds, "id_token", None)
    if not _is_valid_jwt(tok):
        tok = None

    # 2. GCE / Cloud Run / Agent Engine metadata identity endpoint
    if not tok:
        try:
            candidate = id_token.fetch_id_token(req, audience_url)
            if _is_valid_jwt(candidate):
                tok = candidate
        except Exception as exc:
            logger.warning("Metadata fetch_id_token failed (%s); trying IAM generateIdToken", exc)

    # 3. Fallback: IAM Credentials generateIdToken API using runtime SA token
    if not tok:
        sa_email = os.environ.get("AGENT_SA_EMAIL_V2") or getattr(
            creds, "service_account_email", ""
        )
        if sa_email and sa_email != "default":
            iam_url = (
                f"https://iamcredentials.googleapis.com/v1/projects/-/"
                f"serviceAccounts/{sa_email}:generateIdToken"
            )
            iam_req = urllib.request.Request(
                iam_url,
                data=json.dumps(
                    {"audience": audience_url, "includeEmail": True}
                ).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {creds.token}",
                    "Content-Type": "application/json",
                },
            )
            with urllib.request.urlopen(iam_req, timeout=10) as resp:
                candidate = json.loads(resp.read().decode("utf-8")).get("token")
                if _is_valid_jwt(candidate):
                    tok = candidate

    if not tok:
        raise RuntimeError(f"Unable to mint OIDC ID token for {audience_url}")

    _TOKEN_CACHE[audience_url] = (tok, now + _TOKEN_TTL_SECONDS)
    return tok


class CloudRunOIDCMcpToolset(McpToolset):
    """McpToolset subclass that injects fresh Cloud Run OIDC headers unconditionally."""

    def __init__(self, *, url: str, timeout: float = 30.0) -> None:
        parsed = urllib.parse.urlparse(url)
        self._oidc_audience = (
            f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else ""
        )
        super().__init__(
            connection_params=StreamableHTTPConnectionParams(
                url=url,
                timeout=timeout,
            ),
            header_provider=lambda _ctx=None: self._fresh_auth_header(),
            tool_list_cache_ttl_seconds=300,
        )

    def _fresh_auth_header(self) -> Dict[str, str]:
        if (
            not self._oidc_audience.startswith("https://")
            or ".example.run.app" in self._oidc_audience
        ):
            return {}
        return {"Authorization": f"Bearer {_fetch_oidc_bearer_token(self._oidc_audience)}"}

    async def _build_headers(self, readonly_context=None) -> Dict[str, str]:
        headers = dict(await super()._build_headers(readonly_context))
        headers.update(self._fresh_auth_header())
        return headers


TOOLBOX_MCP_V2_URL = os.environ.get(
    "TOOLBOX_MCP_V2_URL", "https://mcp-toolbox-databases-v2.example.run.app/mcp"
)
BQ_MCP_V2_URL = os.environ.get(
    "BQ_MCP_V2_URL", "https://mcp-server-bigquery-v2.example.run.app/mcp"
)
AGENT_MODEL_V2 = os.environ.get("AGENT_MODEL_V2", "gemini-2.5-flash")

toolbox_v2_toolset = CloudRunOIDCMcpToolset(url=TOOLBOX_MCP_V2_URL, timeout=30.0)
bigquery_v2_toolset = CloudRunOIDCMcpToolset(url=BQ_MCP_V2_URL, timeout=30.0)

root_agent = LlmAgent(
    name="sentinel_customer_360_advisor_v2",
    model=AGENT_MODEL_V2,
    description=(
        "Sentinel — Enterprise Customer 360 & Risk Advisor (v2): Cross-cloud "
        "financial ledger, CRM engagement, and ML fraud/churn intelligence advisor."
    ),
    instruction=PROMPT_FILE.read_text(encoding="utf-8"),
    tools=[toolbox_v2_toolset, bigquery_v2_toolset],
)
