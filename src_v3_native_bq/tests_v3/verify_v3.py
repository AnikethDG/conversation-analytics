"""Verification Suite for `v3` (Native BigQuery MCP + MCP Toolbox).

Runs offline guardrail unit tests unconditionally (no cloud credentials needed)
and optionally executes live `https://bigquery.googleapis.com/mcp` + ADK tests
when `--live` is passed.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import urllib.request

V3_ROOT = Path(__file__).resolve().parents[1]
if str(V3_ROOT) not in sys.path:
    sys.path.insert(0, str(V3_ROOT))

from sentinel_customer_360_advisor_v3.agent import (  # noqa: E402
    ALLOWED_BQ_MCP_TOOLS,
    BLOCKED_BQ_MCP_TOOLS,
    CloudRunOIDCMcpToolset,
    GoogleApiOAuthMcpToolset,
    is_operational_aws_tool,
    is_readonly_bq_mcp_tool,
    root_agent,
)


def run_offline_guardrail_tests() -> None:
    print("[TEST 1] Verifying ADK Read-Only Tool Filter on Native BigQuery MCP...")
    for allowed in ALLOWED_BQ_MCP_TOOLS:
        assert is_readonly_bq_mcp_tool(SimpleNamespace(name=allowed)) is True, (
            f"Expected read-only tool '{allowed}' to be allowed"
        )
    for blocked in BLOCKED_BQ_MCP_TOOLS:
        assert is_readonly_bq_mcp_tool(SimpleNamespace(name=blocked)) is False, (
            f"Write tool '{blocked}' MUST be blocked!"
        )
    assert is_readonly_bq_mcp_tool(SimpleNamespace(name="drop_table")) is False
    print(
        f"  [PASS] Allowed {sorted(ALLOWED_BQ_MCP_TOOLS)} | "
        f"Blocked {sorted(BLOCKED_BQ_MCP_TOOLS)} + unknown mutators"
    )

    print("\n[TEST 2] Verifying Operational AWS Filter on MCP Toolbox...")
    assert is_operational_aws_tool(SimpleNamespace(name="pg_get_customer_360_v2")) is True
    assert is_operational_aws_tool(SimpleNamespace(name="mysql_get_customer_engagement_v2")) is True
    assert is_operational_aws_tool(SimpleNamespace(name="bq_top_risk_cohort_v2")) is False
    print("  [PASS] Toolbox cleanly scoped to pg_* and mysql_* (100% BQ -> native MCP)")

    print("\n[TEST 3] Verifying `root_agent` Dual-Auth Toolset Wiring...")
    assert root_agent.name == "sentinel_customer_360_advisor_v3"
    assert len(root_agent.tools) == 2
    assert isinstance(root_agent.tools[0], CloudRunOIDCMcpToolset)
    assert isinstance(root_agent.tools[1], GoogleApiOAuthMcpToolset)
    assert "execute_sql_readonly" in root_agent.instruction
    assert "LIMIT <= 50" in root_agent.instruction
    print("  [PASS] root_agent wired with CloudRunOIDCMcpToolset + GoogleApiOAuthMcpToolset")


async def run_live_tests(project_id: str, toolbox_url: str) -> None:
    from agent_v3.agent_v3 import run_agent_turn_v3
    from sentinel_customer_360_advisor_v3.agent import _fetch_google_oauth_headers

    print(f"\n[TEST 4 · LIVE] Inspecting https://bigquery.googleapis.com/mcp (project={project_id})...")
    hdrs = _fetch_google_oauth_headers(project_id)
    hdrs["Content-Type"] = "application/json"
    hdrs["Accept"] = "application/json, text/event-stream"

    req = urllib.request.Request(
        "https://bigquery.googleapis.com/mcp",
        data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}).encode(),
        headers=hdrs,
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    raw_names = [t["name"] for t in data.get("result", {}).get("tools", [])]
    filtered = [n for n in raw_names if is_readonly_bq_mcp_tool(SimpleNamespace(name=n))]
    print(f"  - Server tools   : {raw_names}")
    print(f"  - Agent-exposed  : {filtered} ('execute_sql' stripped={('execute_sql' not in filtered)})")
    assert "execute_sql" not in filtered

    print("\n[TEST 5 · LIVE] Running End-to-End Cross-Cloud v3 Agent Turn...")
    res = await run_agent_turn_v3(
        prompt=(
            "For customer 'james.smith@example.com', check his AWS Postgres accounts, "
            "AWS MySQL support tickets, and his fraud & churn risk scores in BigQuery ccca."
        ),
        toolbox_mcp_url=toolbox_url,
        bq_project_id=project_id,
    )
    print(f"  - Tools Called : {res['tool_calls']}")
    print(f"  - Latency      : {res['latency_s']}s | Total Tokens: {res['total_tokens']}")
    print(f"  - Answer       : {res['answer'][:280]}...")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="Run live GCP & ADK verification.")
    parser.add_argument("--project", default=os.environ.get("BQ_PROJECT_ID", "agentic-mvp"))
    parser.add_argument(
        "--toolbox-url",
        default=os.environ.get(
            "TOOLBOX_MCP_V3_URL",
            "https://mcp-toolbox-databases-v2-2gjvxmiz3q-uc.a.run.app/mcp",
        ),
    )
    args = parser.parse_args()

    run_offline_guardrail_tests()
    if args.live:
        asyncio.run(run_live_tests(args.project, args.toolbox_url))
    print("\nALL v3 VERIFICATION CHECKS PASSED!")


if __name__ == "__main__":
    main()
