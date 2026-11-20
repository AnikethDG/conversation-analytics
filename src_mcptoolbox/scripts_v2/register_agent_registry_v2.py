#!/usr/bin/env python3
"""Registers `mcp-toolbox-databases-v2` and `mcp-server-bigquery-v2` in GCP Agent Registry.

Enables `agentregistry.googleapis.com` in the target project (`agentic-mvp` by default),
fetches live `tools/list` specifications from both IAM-protected Cloud Run MCP endpoints
(with static schema fallback under the 10 KB Agent Registry limit), upserts both writable
`Service` resources in Agent Registry, and verifies the projected `McpServer` catalog entries.

Usage:
    # 1. Ensure Application Default Credentials are active for `agentic-mvp`:
    gcloud auth application-default login

    # 2. Register both MCP servers in Agent Registry:
    ./.venv/bin/python src_mcptoolbox/scripts_v2/register_agent_registry_v2.py
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import ssl
import subprocess
import sys
import time
from typing import Any, Dict, List
import urllib.error
import urllib.parse
import urllib.request

import certifi
import google.auth
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2 import id_token

REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = REPO_ROOT / "src_mcptoolbox" / "sentinel_customer_360_advisor_v2" / ".env"
SSL_CTX = ssl.create_default_context(cafile=certifi.where())


def _load_dotenv(path: Path) -> Dict[str, str]:
    values: Dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        values[k.strip()] = v.strip().strip('"').strip("'")
    return values


def _clean_nulls_and_meta(obj: Any) -> Any:
    """Strips None values and `_meta` keys per Agent Registry TOOL_SPEC rules."""
    if isinstance(obj, dict):
        return {
            k: _clean_nulls_and_meta(v)
            for k, v in obj.items()
            if v is not None and k != "_meta"
        }
    if isinstance(obj, list):
        return [_clean_nulls_and_meta(item) for item in obj if item is not None]
    return obj


def _fallback_toolbox_spec() -> Dict[str, Any]:
    """Fallback One MCP TOOL_SPEC matching `mcp_toolbox_v2/tools_v2.yaml` (< 10 KB)."""
    str_prop = lambda desc: {"type": "string", "description": desc}
    return {
        "tools": [
            {
                "name": "pg_get_customer_360_v2",
                "description": "Look up a customer in AWS PostgreSQL (finance_db) by email or full name.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"search_term": str_prop("Customer email or full name.")},
                    "required": ["search_term"],
                },
            },
            {
                "name": "pg_batch_accounts_by_emails_v2",
                "description": "Batch lookup of AWS PostgreSQL accounts and balances for up to 50 comma-separated emails.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"emails_csv": str_prop("Comma-separated customer emails.")},
                    "required": ["emails_csv"],
                },
            },
            {
                "name": "pg_top_customers_by_balance_v2",
                "description": "Retrieve top customers in AWS PostgreSQL ordered by account balance (max 25 rows).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "account_type": str_prop("'checking', 'savings', 'credit', or 'all'."),
                        "sort_order": str_prop("'desc' or 'asc'."),
                        "row_limit": {"type": "integer", "description": "Max rows (1 to 25)."},
                    },
                    "required": ["account_type", "sort_order", "row_limit"],
                },
            },
            {
                "name": "pg_ledger_summary_kpis_v2",
                "description": "Compute aggregated account counts and total/average balances across AWS PostgreSQL finance_db.",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "mysql_get_customer_engagement_v2",
                "description": "Fetch support tickets and campaign responses from AWS MySQL (engagement_db) for a customer_email.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "customer_email": str_prop("Customer email address."),
                        "customer_email_repeat": str_prop("Same customer email address."),
                    },
                    "required": ["customer_email", "customer_email_repeat"],
                },
            },
            {
                "name": "mysql_batch_engagement_by_emails_v2",
                "description": "Batch lookup of tickets and campaign responses in AWS MySQL for up to 50 emails.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "emails_csv_tickets": str_prop("Comma-separated emails without spaces."),
                        "emails_csv_campaigns": str_prop("Same comma-separated emails without spaces."),
                    },
                    "required": ["emails_csv_tickets", "emails_csv_campaigns"],
                },
            },
            {
                "name": "mysql_engagement_summary_kpis_v2",
                "description": "Return aggregated ticket counts by status and campaign response counts across AWS MySQL.",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "bq_get_customer_risk_and_events_v2",
                "description": "Fetch churn/fraud risk scores and up to 5 recent app events from BigQuery ccca by customer_email.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"customer_email": str_prop("Customer email address.")},
                    "required": ["customer_email"],
                },
            },
            {
                "name": "bq_batch_risk_by_emails_v2",
                "description": "Batch lookup of risk scores and app event counts in BigQuery ccca for up to 50 emails.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"emails_csv": str_prop("Comma-separated emails without spaces.")},
                    "required": ["emails_csv"],
                },
            },
            {
                "name": "bq_top_risk_cohort_v2",
                "description": "Prune 50M-row BigQuery customer_risk_profiles to top 10 high-risk customer_email keys.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "min_fraud_score": {"type": "number", "description": "Min fraud_risk_score (0.0-1.0)."},
                        "min_churn_score": {"type": "number", "description": "Min churn_risk_score (0.0-1.0)."},
                    },
                    "required": ["min_fraud_score", "min_churn_score"],
                },
            },
        ]
    }


def _fallback_bigquery_spec() -> Dict[str, Any]:
    """Fallback One MCP TOOL_SPEC matching `mcp_bigquery_v2/main_v2.py`."""
    return {
        "tools": [
            {
                "name": "query_bigquery_v2",
                "description": (
                    "Execute a guardrailed read-only GoogleSQL SELECT query on BigQuery dataset "
                    "'ccca' (pre-validated with dry_run byte budget and capped at 50 rows)."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Single-statement GoogleSQL SELECT query.",
                        },
                        "max_scan_mb": {
                            "type": "number",
                            "description": "Optional per-query scan budget override in MiB.",
                        },
                    },
                    "required": ["query"],
                },
            }
        ]
    }


def get_gcp_access_token() -> tuple[Any, str]:
    """Obtains an OAuth2 access token from ADC (or CLOUDSDK_AUTH_ACCESS_TOKEN)."""
    req = Request()
    creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    creds.refresh(req)
    return creds, creds.token


def get_cloud_run_oidc_token(creds: Any, audience_url: str) -> str:
    """Obtains a Google-signed OIDC ID token for IAM-authenticated Cloud Run."""
    tok = getattr(creds, "id_token", None)
    if isinstance(tok, str) and tok.count(".") == 2:
        return tok
    try:
        return id_token.fetch_id_token(Request(), audience_url)
    except Exception:
        env = os.environ.copy()
        env["CLOUDSDK_AUTH_ACCESS_TOKEN"] = creds.token
        env["CLOUDSDK_METRICS_ENVIRONMENT"] = (
            env.get("CLOUDSDK_METRICS_ENVIRONMENT", "") + " datacloud.antigravity"
        ).strip()
        return subprocess.check_output(
            ["gcloud", "--quiet", "auth", "print-identity-token"], env=env, text=True
        ).strip()


def fetch_live_mcp_tool_spec(
    mcp_url: str, creds: Any, fallback_spec: Dict[str, Any]
) -> Dict[str, Any]:
    """Calls MCP `initialize` + `tools/list` on Cloud Run, falling back cleanly if needed."""
    parsed = urllib.parse.urlparse(mcp_url)
    audience = f"{parsed.scheme}://{parsed.netloc}"
    try:
        oidc_tok = get_cloud_run_oidc_token(creds, audience)
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": f"Bearer {oidc_tok}",
        }
        init_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "agent_registry_onboarding", "version": "1.0"},
            },
        }
        req1 = urllib.request.Request(
            mcp_url, data=json.dumps(init_payload).encode("utf-8"), headers=headers
        )
        with urllib.request.urlopen(req1, timeout=20, context=SSL_CTX) as r1:
            r1.read()
            sess_id = r1.headers.get("Mcp-Session-Id") or r1.headers.get("mcp-session-id")
        if sess_id:
            headers["Mcp-Session-Id"] = sess_id

        list_payload = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
        req2 = urllib.request.Request(
            mcp_url, data=json.dumps(list_payload).encode("utf-8"), headers=headers
        )
        with urllib.request.urlopen(req2, timeout=20, context=SSL_CTX) as r2:
            raw = r2.read().decode("utf-8")

        result_obj = None
        for line in raw.splitlines():
            if line.startswith("data:"):
                line = line[5:].strip()
            if line.startswith("{"):
                cand = json.loads(line)
                if "result" in cand:
                    result_obj = cand["result"]
                    break
        if result_obj is None:
            result_obj = json.loads(raw)["result"]

        spec = _clean_nulls_and_meta({"tools": result_obj.get("tools", [])})
        encoded = json.dumps(spec, separators=(",", ":")).encode("utf-8")
        if len(encoded) <= 10000 and spec.get("tools"):
            print(
                f"  [OK] Fetched live tools/list from {mcp_url} "
                f"({len(spec['tools'])} tools, {len(encoded)} bytes)"
            )
            return spec
        print(
            f"  [INFO] Live tools/list size ({len(encoded)} bytes) exceeds 10KB cap; "
            "using compact spec."
        )
    except Exception as exc:
        print(f"  [INFO] Using compact static tool spec for {mcp_url} ({exc})")

    return _clean_nulls_and_meta(fallback_spec)


def api_request(
    method: str,
    url: str,
    access_token: str,
    project_id: str,
    body: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "x-goog-user-project": project_id,
        "Content-Type": "application/json",
    }
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=30, context=SSL_CTX) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw.strip() else {}


def wait_for_lro(
    op: Dict[str, Any], base_api: str, access_token: str, project_id: str
) -> Dict[str, Any]:
    if op.get("done"):
        if "error" in op:
            raise RuntimeError(f"Operation failed: {op['error']}")
        return op
    op_name = op["name"]
    poll_url = f"{base_api}/v1/{op_name}"
    for _ in range(30):
        time.sleep(2)
        cur = api_request("GET", poll_url, access_token, project_id)
        if cur.get("done"):
            if "error" in cur:
                raise RuntimeError(f"Operation failed: {cur['error']}")
            return cur
    raise TimeoutError(f"Timed out waiting for operation {op_name}")


def enable_agent_registry_api(access_token: str, project_id: str) -> None:
    print(f"[1/3] Enabling agentregistry.googleapis.com on project '{project_id}'...")
    url = (
        f"https://serviceusage.googleapis.com/v1/projects/{project_id}"
        "/services/agentregistry.googleapis.com:enable"
    )
    op = api_request("POST", url, access_token, project_id, {})
    if op.get("name") and not op.get("name", "").endswith("operations/noop.DONE_OPERATION"):
        wait_for_lro(op, "https://serviceusage.googleapis.com", access_token, project_id)
    print("  [OK] agentregistry.googleapis.com is enabled.")


def upsert_mcp_service(
    *,
    project_id: str,
    location: str,
    service_id: str,
    display_name: str,
    description: str,
    mcp_url: str,
    tool_spec: Dict[str, Any],
    access_token: str,
) -> Dict[str, Any]:
    parent = f"projects/{project_id}/locations/{location}"
    service_body = {
        "displayName": display_name,
        "description": description,
        "interfaces": [
            {
                "url": mcp_url,
                "protocolBinding": "JSONRPC",
            }
        ],
        "mcpServerSpec": {
            "type": "TOOL_SPEC",
            "content": tool_spec,
        },
    }

    create_url = (
        f"https://agentregistry.googleapis.com/v1/{parent}/services"
        f"?serviceId={urllib.parse.quote(service_id)}"
    )
    try:
        op = api_request("POST", create_url, access_token, project_id, service_body)
        res = wait_for_lro(op, "https://agentregistry.googleapis.com", access_token, project_id)
        print(f"  [OK] Created Agent Registry Service: {parent}/services/{service_id}")
        return res.get("response", {})
    except urllib.error.HTTPError as err:
        err_text = err.read().decode("utf-8", errors="replace")
        if err.code == 409:
            patch_url = (
                f"https://agentregistry.googleapis.com/v1/{parent}/services/{service_id}"
                "?updateMask=displayName,description,interfaces,mcpServerSpec"
            )
            op = api_request("PATCH", patch_url, access_token, project_id, service_body)
            res = wait_for_lro(op, "https://agentregistry.googleapis.com", access_token, project_id)
            print(f"  [OK] Updated existing Agent Registry Service: {parent}/services/{service_id}")
            return res.get("response", {})
        raise RuntimeError(
            f"Agent Registry HTTP {err.code} for '{service_id}': {err_text}"
        ) from err


def main() -> int:
    dotenv = _load_dotenv(ENV_FILE)
    parser = argparse.ArgumentParser(
        description="Register v2 Cloud Run MCP servers in Google Cloud Agent Registry."
    )
    parser.add_argument(
        "--project",
        default=os.environ.get("PROJECT_ID", "agentic-mvp"),
        help="Target GCP project ID (default: agentic-mvp).",
    )
    parser.add_argument(
        "--location",
        default=os.environ.get("AGENT_REGISTRY_LOCATION", "global"),
        help="Agent Registry location, e.g. 'global' or 'us-central1' (default: global).",
    )
    parser.add_argument(
        "--toolbox-url",
        default=os.environ.get("TOOLBOX_MCP_V2_URL")
        or dotenv.get(
            "TOOLBOX_MCP_V2_URL",
            "https://mcp-toolbox-databases-v2-2gjvxmiz3q-uc.a.run.app/mcp",
        ),
    )
    parser.add_argument(
        "--bq-url",
        default=os.environ.get("BQ_MCP_V2_URL")
        or dotenv.get(
            "BQ_MCP_V2_URL",
            "https://mcp-server-bigquery-v2-2gjvxmiz3q-uc.a.run.app/mcp",
        ),
    )
    parser.add_argument(
        "--dry-run-specs",
        action="store_true",
        help="Validate and print local tool spec sizes without calling GCP APIs.",
    )
    args = parser.parse_args()

    if args.dry_run_specs:
        tb_bytes = len(json.dumps(_fallback_toolbox_spec(), separators=(",", ":")))
        bq_bytes = len(json.dumps(_fallback_bigquery_spec(), separators=(",", ":")))
        print(f"Toolbox spec size : {tb_bytes} bytes (limit: 10240)")
        print(f"BigQuery spec size: {bq_bytes} bytes (limit: 10240)")
        return 0

    try:
        creds, access_token = get_gcp_access_token()
    except RefreshError as exc:
        print(
            "ERROR: Application Default Credentials for 'agentic-mvp' have expired.\n"
            "Run `gcloud auth application-default login` (selecting your Argolis "
            "account) and re-run this script.\n"
            f"Details: {exc}",
            file=sys.stderr,
        )
        return 2

    enable_agent_registry_api(access_token, args.project)

    print("\n[2/3] Inspecting MCP tool specifications & registering services...")
    tb_spec = fetch_live_mcp_tool_spec(args.toolbox_url, creds, _fallback_toolbox_spec())
    bq_spec = fetch_live_mcp_tool_spec(args.bq_url, creds, _fallback_bigquery_spec())

    tb_svc = upsert_mcp_service(
        project_id=args.project,
        location=args.location,
        service_id="mcp-toolbox-databases-v2",
        display_name="MCP Toolbox Databases v2 (Postgres, MySQL, BigQuery)",
        description=(
            "Official Google MCP Toolbox (v2) exposing 10 pooled, parameterized "
            "read-only tools across AWS PostgreSQL (finance_db), AWS MySQL "
            "(engagement_db), and GCP BigQuery (ccca)."
        ),
        mcp_url=args.toolbox_url,
        tool_spec=tb_spec,
        access_token=access_token,
    )
    bq_svc = upsert_mcp_service(
        project_id=args.project,
        location=args.location,
        service_id="mcp-server-bigquery-v2",
        display_name="Guardrailed BigQuery MCP Server v2",
        description=(
            "Guardrailed read-only GoogleSQL MCP server for BigQuery dataset ccca "
            "with pre-flight dry_run byte budget enforcement and a 50-row context cap."
        ),
        mcp_url=args.bq_url,
        tool_spec=bq_spec,
        access_token=access_token,
    )

    print("\n[3/3] Verifying projected McpServer entries in Agent Registry...")
    list_url = (
        f"https://agentregistry.googleapis.com/v1/projects/{args.project}"
        f"/locations/{args.location}/mcpServers"
    )
    catalog = api_request("GET", list_url, access_token, args.project)
    for srv in catalog.get("mcpServers", []):
        name = srv.get("name", "")
        if any(k in name for k in ("mcp-toolbox-databases-v2", "mcp-server-bigquery-v2")):
            tools_cnt = len(srv.get("tools", []))
            iface_urls = [i.get("url") for i in srv.get("interfaces", [])]
            print(f"  - {name} | displayName='{srv.get('displayName')}' | tools={tools_cnt} | urls={iface_urls}")

    if tb_svc.get("registryResource"):
        print(f"  Projected Toolbox McpServer : {tb_svc['registryResource']}")
    if bq_svc.get("registryResource"):
        print(f"  Projected BigQuery McpServer: {bq_svc['registryResource']}")

    print("\nRegistration in Agent Registry completed successfully!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
