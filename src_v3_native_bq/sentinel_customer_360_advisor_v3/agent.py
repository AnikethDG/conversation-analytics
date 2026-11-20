"""Sentinel — Enterprise Customer 360 & Risk Advisor_v3 (Native BigQuery MCP).

Eliminates the custom `mcp-server-bigquery-v2` Cloud Run container by pairing:
  1. `CloudRunOIDCMcpToolset` -> Google MCP Toolbox on Cloud Run (AWS Postgres & MySQL)
     authenticated via auto-rotating Google-signed OIDC ID tokens.
  2. `GoogleApiOAuthMcpToolset` -> BigQuery's native managed remote MCP server
     (`https://bigquery.googleapis.com/mcp`) authenticated via auto-refreshing
     OAuth2 access tokens + `x-goog-user-project`, with `is_readonly_bq_mcp_tool`
     strictly blocking write-capable `execute_sql` at the ADK toolset boundary.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import time
from typing import Any, Dict, Tuple
import urllib.parse
import urllib.request

from google.adk.agents import LlmAgent
from google.adk.models import Gemini
from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams
import google.auth
from google.auth.transport.requests import Request
from google.oauth2 import id_token

logger = logging.getLogger("sentinel_advisor_v3")

PROMPT_FILE = Path(__file__).with_name("prompt_v3.md")

_OIDC_CACHE: Dict[str, Tuple[str, float]] = {}
_OAUTH_CACHE: Dict[str, Tuple[str, str | None, float]] = {}
_TOKEN_TTL_SECONDS = 2700.0  # Refresh every 45 mins (tokens valid 60 mins)

# Write/mutating tools on https://bigquery.googleapis.com/mcp that MUST NEVER
# be exposed to the LLM. Only read-only SQL & schema discovery tools pass through.
BLOCKED_BQ_MCP_TOOLS = frozenset({"execute_sql"})

# Explicit read-only allowlist documented for BigQuery's native MCP server:
ALLOWED_BQ_MCP_TOOLS = frozenset(
    {
        "list_dataset_ids",
        "get_dataset_info",
        "list_table_ids",
        "get_table_info",
        "execute_sql_readonly",
        "get_query_results",
    }
)


def is_readonly_bq_mcp_tool(tool: Any, readonly_context: Any = None) -> bool:
    """ADK ToolPredicate enforcing strict read-only tool exposure on native BQ MCP."""
    name = getattr(tool, "name", "")
    if not name or name in BLOCKED_BQ_MCP_TOOLS:
        return False
    return name in ALLOWED_BQ_MCP_TOOLS


def is_operational_aws_tool(tool: Any, readonly_context: Any = None) -> bool:
    """Filters MCP Toolbox to AWS Postgres & MySQL tools so 100% of BQ uses native MCP."""
    name = getattr(tool, "name", "")
    return not name.startswith("bq_")


def _is_valid_jwt(val: object) -> bool:
    return isinstance(val, str) and len(val.strip()) > 40 and val.count(".") == 2


def _fetch_oidc_bearer_token(audience_url: str) -> str:
    """Fetches and caches a Google-signed OIDC ID token for Cloud Run IAM auth."""
    now = time.monotonic()
    cached = _OIDC_CACHE.get(audience_url)
    if cached and now < cached[1]:
        return cached[0]

    req = Request()
    creds, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    creds.refresh(req)

    tok = getattr(creds, "id_token", None)
    if not _is_valid_jwt(tok):
        tok = None

    if not tok:
        try:
            candidate = id_token.fetch_id_token(req, audience_url)
            if _is_valid_jwt(candidate):
                tok = candidate
        except Exception as exc:
            logger.warning(
                "Metadata fetch_id_token failed (%s); trying IAM generateIdToken", exc
            )

    if not tok:
        sa_email = (
            os.environ.get("AGENT_SA_EMAIL_V3")
            or os.environ.get("AGENT_SA_EMAIL_V2")
            or getattr(creds, "service_account_email", "")
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

    _OIDC_CACHE[audience_url] = (tok, now + _TOKEN_TTL_SECONDS)
    return tok


def _fetch_google_oauth_headers(billing_project_id: str | None = None) -> Dict[str, str]:
    """Fetches and caches an OAuth2 access token + quota project for `*.googleapis.com/mcp`."""
    cache_key = billing_project_id or "default"
    now = time.monotonic()
    cached = _OAUTH_CACHE.get(cache_key)
    if cached and now < cached[2]:
        token, quota_proj, _ = cached
    else:
        req = Request()
        creds, adc_project = google.auth.default(
            scopes=[
                "https://www.googleapis.com/auth/bigquery",
                "https://www.googleapis.com/auth/cloud-platform",
            ]
        )
        creds.refresh(req)
        if not creds.token:
            raise RuntimeError("Unable to obtain Google OAuth2 access token for BigQuery MCP")
        quota_proj = (
            billing_project_id
            or getattr(creds, "quota_project_id", None)
            or adc_project
        )
        token = creds.token
        _OAUTH_CACHE[cache_key] = (token, quota_proj, now + _TOKEN_TTL_SECONDS)

    headers: Dict[str, str] = {"Authorization": f"Bearer {token}"}
    if quota_proj:
        headers["x-goog-user-project"] = quota_proj
    return headers


class CloudRunOIDCMcpToolset(McpToolset):
    """McpToolset subclass injecting fresh Cloud Run OIDC ID tokens per request."""

    def __init__(
        self,
        *,
        url: str,
        timeout: float = 30.0,
        tool_filter: Any = None,
    ) -> None:
        parsed = urllib.parse.urlparse(url)
        self._oidc_audience = (
            f"{parsed.scheme}://{parsed.netloc}"
            if parsed.scheme and parsed.netloc
            else ""
        )
        super().__init__(
            connection_params=StreamableHTTPConnectionParams(
                url=url,
                timeout=timeout,
            ),
            tool_filter=tool_filter,
            header_provider=lambda _ctx=None: self._fresh_auth_header(),
            tool_list_cache_ttl_seconds=300,
        )

    def _fresh_auth_header(self) -> Dict[str, str]:
        if (
            not self._oidc_audience.startswith("https://")
            or ".example.run.app" in self._oidc_audience
        ):
            return {}
        return {
            "Authorization": f"Bearer {_fetch_oidc_bearer_token(self._oidc_audience)}"
        }

    async def _build_headers(self, readonly_context=None) -> Dict[str, str]:
        headers = dict(await super()._build_headers(readonly_context))
        headers.update(self._fresh_auth_header())
        return headers


class GoogleApiOAuthMcpToolset(McpToolset):
    """McpToolset subclass for Google-managed `*.googleapis.com/mcp` remote servers.

    Unlike Cloud Run (which requires OIDC ID tokens), Google Cloud native MCP
    endpoints (`https://bigquery.googleapis.com/mcp`) authenticate with standard
    OAuth2 access tokens + `x-goog-user-project` and enforce IAM (`roles/mcp.toolUser`).
    """

    def __init__(
        self,
        *,
        url: str = "https://bigquery.googleapis.com/mcp",
        billing_project_id: str | None = None,
        timeout: float = 30.0,
        tool_filter: Any = is_readonly_bq_mcp_tool,
    ) -> None:
        self._billing_project_id = billing_project_id
        super().__init__(
            connection_params=StreamableHTTPConnectionParams(
                url=url,
                timeout=timeout,
            ),
            tool_filter=tool_filter,
            header_provider=lambda _ctx=None: self._fresh_oauth_headers(),
            tool_list_cache_ttl_seconds=300,
        )

    def _fresh_oauth_headers(self) -> Dict[str, str]:
        return _fetch_google_oauth_headers(self._billing_project_id)

    async def _build_headers(self, readonly_context=None) -> Dict[str, str]:
        headers = dict(await super()._build_headers(readonly_context))
        headers.update(self._fresh_oauth_headers())
        return headers


TOOLBOX_MCP_V3_URL = os.environ.get(
    "TOOLBOX_MCP_V3_URL",
    os.environ.get(
        "TOOLBOX_MCP_V2_URL", "https://mcp-toolbox-databases-v2.example.run.app/mcp"
    ),
)
BQ_NATIVE_MCP_URL = os.environ.get(
    "BQ_NATIVE_MCP_URL", "https://bigquery.googleapis.com/mcp"
)
BQ_PROJECT_ID = (
    os.environ.get("BQ_PROJECT_ID")
    or os.environ.get("GOOGLE_CLOUD_PROJECT")
    or "agentic-mvp"
)
ALLOW_TOOLBOX_BQ_SHORTCUTS = (
    os.environ.get("ALLOW_TOOLBOX_BQ_SHORTCUTS", "false").lower() == "true"
)
AGENT_MODEL_V3 = os.environ.get("AGENT_MODEL_V3", "gemini-3-flash-preview")
AGENT_MODEL_LOCATION_V3 = os.environ.get("AGENT_MODEL_LOCATION_V3", "global")

toolbox_v3_toolset = CloudRunOIDCMcpToolset(
    url=TOOLBOX_MCP_V3_URL,
    timeout=30.0,
    tool_filter=None if ALLOW_TOOLBOX_BQ_SHORTCUTS else is_operational_aws_tool,
)

bigquery_native_mcp_toolset = GoogleApiOAuthMcpToolset(
    url=BQ_NATIVE_MCP_URL,
    billing_project_id=BQ_PROJECT_ID,
    timeout=30.0,
    tool_filter=is_readonly_bq_mcp_tool,
)

raw_instruction = PROMPT_FILE.read_text(encoding="utf-8").replace(
    "{{BQ_PROJECT_ID}}", BQ_PROJECT_ID
)

root_agent = LlmAgent(
    name="sentinel_customer_360_advisor_v3",
    model=Gemini(
        model=AGENT_MODEL_V3,
        client_kwargs={"location": AGENT_MODEL_LOCATION_V3},
    ),
    description=(
        "Sentinel — Enterprise Customer 360 & Risk Advisor (v3): Cross-cloud "
        "AWS operational ledger/CRM via Google MCP Toolbox + Google's native "
        "managed BigQuery MCP server (bigquery.googleapis.com/mcp)."
    ),
    instruction=raw_instruction,
    tools=[toolbox_v3_toolset, bigquery_native_mcp_toolset],
)
