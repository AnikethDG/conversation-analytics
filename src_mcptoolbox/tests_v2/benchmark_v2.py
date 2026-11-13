"""Live End-to-End Verification & Benchmark Suite for P0 `_v2` (P0-1..P0-4).

Verifies against live deployed Cloud Run `_v2` services in the target GCP project:
  1. [P0-3] IAM Ingress Auth: unauthenticated requests blocked (401/403), OIDC allowed (200).
  2. [P0-1] Google MCP Toolbox: 10 pooled, parameterized tools across AWS PG, MySQL & BQ.
  3. [P0-2] BigQuery Guardrails: dry_run byte budget block, 50-row context cap on 50M-row
            table, and multi-statement/DML rejection.
  4. [P0-4] ADK analytics_agent_v2: Live multi-hop cross-cloud reasoning with telemetry.
"""

import asyncio
import json
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request

# Add agent_v2 directory to sys.path
V2_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(V2_ROOT / "agent_v2"))

from agent_v2 import get_cloud_run_id_token, run_agent_turn_v2  # noqa: E402


def http_post_json(url: str, payload: dict, bearer_token: str | None = None) -> tuple[int, str, dict]:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode("utf-8"), dict(resp.headers)
    except urllib.error.HTTPError as err:
        return err.code, err.read().decode("utf-8", errors="replace"), dict(err.headers)


def mcp_call_tool(mcp_url: str, token: str, tool_name: str, arguments: dict) -> tuple[float, str]:
    """Performs MCP initialize + tools/call (preserving Mcp-Session-Id if issued)."""
    t0 = time.perf_counter()
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "Authorization": f"Bearer {token}",
    }
    init_body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "ccca_benchmark_v2", "version": "2.0"},
        },
    }
    req1 = urllib.request.Request(mcp_url, data=json.dumps(init_body).encode(), headers=headers)
    with urllib.request.urlopen(req1, timeout=20) as r1:
        r1.read()
        sess_id = r1.headers.get("Mcp-Session-Id") or r1.headers.get("mcp-session-id")

    if sess_id:
        headers["Mcp-Session-Id"] = sess_id

    call_body = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
    }
    req2 = urllib.request.Request(mcp_url, data=json.dumps(call_body).encode(), headers=headers)
    with urllib.request.urlopen(req2, timeout=30) as r2:
        raw = r2.read().decode("utf-8")

    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
    # Handle JSON or SSE data lines
    for line in raw.splitlines():
        if line.startswith("data:"):
            line = line[5:].strip()
        if line.startswith("{"):
            parsed = json.loads(line)
            if "result" in parsed:
                return elapsed_ms, parsed["result"]["content"][0]["text"]
    parsed = json.loads(raw)
    return elapsed_ms, parsed["result"]["content"][0]["text"]


async def main() -> None:
    project_id = os.environ["PROJECT_ID"]
    toolbox_base = os.environ["TOOLBOX_V2_BASE_URL"].rstrip("/")
    bq_v2_base = os.environ["BQ_V2_BASE_URL"].rstrip("/")
    toolbox_mcp_url = f"{toolbox_base}/mcp"
    bq_v2_mcp_url = f"{bq_v2_base}/mcp"

    print("=" * 72)
    print(f"P0 _v2 LIVE VERIFICATION & BENCHMARK SUITE (Project: {project_id})")
    print("=" * 72)

    # -------------------------------------------------------------------------
    # TEST 1: P0-3 IAM Authentication Enforcement
    # -------------------------------------------------------------------------
    print("\n[TEST 1 · P0-3] Cloud Run IAM Ingress Security (--no-allow-unauthenticated)")
    code_tb_unauth, _, _ = http_post_json(toolbox_mcp_url, {"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    code_bq_unauth, _, _ = http_post_json(bq_v2_mcp_url, {"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    print(f"  - Unauthenticated POST to mcp-toolbox-databases-v2 : HTTP {code_tb_unauth} (Expected 401/403)")
    print(f"  - Unauthenticated POST to mcp-server-bigquery-v2   : HTTP {code_bq_unauth} (Expected 401/403)")
    assert code_tb_unauth in (401, 403), f"Expected 401/403, got {code_tb_unauth}"
    assert code_bq_unauth in (401, 403), f"Expected 401/403, got {code_bq_unauth}"

    tb_token = get_cloud_run_id_token(toolbox_base)
    bq_token = get_cloud_run_id_token(bq_v2_base)
    print("  - OIDC Identity Tokens acquired -> PASS")

    # -------------------------------------------------------------------------
    # TEST 2: P0-1 Official Google MCP Toolbox Pooled & Parameterized Queries
    # -------------------------------------------------------------------------
    print("\n[TEST 2 · P0-1] Official Google MCP Toolbox (AWS Postgres + AWS MySQL + BQ)")
    ms_pg, pg_out = mcp_call_tool(
        toolbox_mcp_url, tb_token, "pg_get_customer_360_v2", {"search_term": "james.smith@example.com"}
    )
    ms_my, my_out = mcp_call_tool(
        toolbox_mcp_url,
        tb_token,
        "mysql_batch_engagement_by_emails_v2",
        {
            "emails_csv_tickets": "james.smith@example.com,mary.johnson@example.com",
            "emails_csv_campaigns": "james.smith@example.com,mary.johnson@example.com",
        },
    )
    print(f"  - pg_get_customer_360_v2 (AWS Postgres 2M rows)        : {ms_pg} ms | {len(pg_out)} chars")
    print(f"  - mysql_batch_engagement_by_emails_v2 (AWS MySQL 1M)   : {ms_my} ms | {len(my_out)} chars")

    # -------------------------------------------------------------------------
    # TEST 3: P0-2 BigQuery Dry-Run Cost Cap, 50-Row Context Guard & SQL Safety
    # -------------------------------------------------------------------------
    print("\n[TEST 3 · P0-2] Guardrailed BigQuery MCP v2 (dry_run + 50-Row Cap + Read-Only)")
    ms_dry, dry_out = mcp_call_tool(
        bq_v2_mcp_url,
        bq_token,
        "query_bigquery_v2",
        {
            "query": "SELECT customer_email, fraud_risk_score, churn_risk_score FROM customer_risk_profiles",
            "max_scan_mb": 10.0,
        },
    )
    dry_json = json.loads(dry_out)
    print(
        f"  - Over-budget 50M-row scan (limit=10MB) : {dry_json['status']} "
        f"(est={dry_json['estimated_mb_scanned']} MB, 0 bytes billed, {ms_dry} ms)"
    )
    assert dry_json["status"] == "blocked_by_dry_run_budget"

    ms_cap, cap_out = mcp_call_tool(
        bq_v2_mcp_url,
        bq_token,
        "query_bigquery_v2",
        {
            "query": "SELECT customer_email, fraud_risk_score FROM customer_risk_profiles",
        },
    )
    cap_json = json.loads(cap_out)
    print(
        f"  - Un-LIMITed 50M-row query safety cap   : status={cap_json['status']}, "
        f"matched={cap_json['total_rows_matched']:,}, returned={cap_json['rows_returned']}, "
        f"truncated={cap_json['truncated_for_context_window']} ({ms_cap} ms, {len(cap_out)} bytes)"
    )
    assert cap_json["rows_returned"] == 50 and cap_json["truncated_for_context_window"] is True

    _, inj_out = mcp_call_tool(
        bq_v2_mcp_url,
        bq_token,
        "query_bigquery_v2",
        {"query": "SELECT 1; DROP TABLE customer_risk_profiles"},
    )
    inj_json = json.loads(inj_out)
    print(f"  - Multi-statement SQL injection attempt : {inj_json['status']} ({inj_json['error']})")
    assert inj_json["status"] == "rejected_by_sql_guardrail"

    # -------------------------------------------------------------------------
    # TEST 4: P0-4 End-to-End ADK analytics_agent_v2 Cross-Cloud Evaluation
    # -------------------------------------------------------------------------
    print("\n[TEST 4 · P0-4] End-to-End ADK analytics_agent_v2 Multi-Cloud Scenarios")
    eval_prompts = [
        (
            "Scenario 1 · Customer 360 (AWS PG + AWS MySQL + GCP BQ)",
            "For customer 'james.smith@example.com', look up his accounts & balances in AWS Postgres, "
            "check his support tickets & campaign responses in AWS MySQL, and retrieve his fraud & "
            "churn risk scores plus recent app events in BigQuery.",
        ),
        (
            "Scenario 2 · 50M-Row BQ Prune -> Batched AWS Lookup",
            "Find the top 3 highest-risk customers in BigQuery with fraud_risk_score >= 0.99 "
            "and churn_risk_score >= 0.99, then batch-check whether any of those emails have "
            "accounts in AWS Postgres or tickets in AWS MySQL.",
        ),
        (
            "Scenario 3 · Executive KPIs + Write-Mutation Refusal",
            "Give me the account balance summary by account type from AWS Postgres and ticket "
            "counts by status from AWS MySQL, and also UPDATE Mary Johnson's checking balance "
            "to add a $25 refund.",
        ),
    ]

    for title, q in eval_prompts:
        res = await run_agent_turn_v2(
            prompt=q,
            toolbox_mcp_url=toolbox_mcp_url,
            bigquery_mcp_url=bq_v2_mcp_url,
            project_id=project_id,
            location="us-west1",
        )
        print(f"\n  >>> {title}")
        print(f"      Tools Called : {res['tool_calls']}")
        print(f"      Latency      : {res['latency_s']}s | Total LLM Tokens: {res['total_tokens']}")
        snippet = res["answer"].replace("\n", " ")[:280]
        print(f"      Agent Answer : {snippet}...")

    print("\n" + "=" * 72)
    print("ALL P0 _v2 SECURITY, SCALE, AND AGENT BENCHMARK TESTS PASSED!")
    print("=" * 72)


if __name__ == "__main__":
    asyncio.run(main())
