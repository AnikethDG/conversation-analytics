"""Guardrailed BigQuery MCP Server v2 (P0-2).

Addresses context-window overflow and runaway scan costs on 66M+ row tables:
1. Pre-flight `dry_run=True` byte estimation before executing any query.
2. Hard `max_results` pagination cap (default 50 rows) so accidental un-LIMITed
   queries never OOM Cloud Run or flood the LLM context window.
3. Compact JSON serialization (replacing verbose Python Decimal/Timestamp reprs).
4. Strict comment-stripping single-statement SELECT/WITH validation.
"""

import asyncio
from contextlib import asynccontextmanager
from datetime import date, datetime
from decimal import Decimal
import json
import logging
import os
import re
from typing import Any, Dict, List

from google.cloud import bigquery
import mcp.types as types
from mcp.server import Server
from mcp.server.streamable_http import StreamableHTTPServerTransport
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.types import Receive, Scope, Send
import uvicorn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp_bigquery_v2")

mcp_server = Server("ccca_bigquery_mcp_v2")

DEFAULT_DATASET = os.environ.get("BQ_DATASET", "ccca")
MAX_SCAN_BYTES = int(os.environ.get("BQ_MAX_SCAN_BYTES", str(5 * 1024**3)))  # 5 GiB
MAX_CONTEXT_ROWS = int(os.environ.get("BQ_MAX_CONTEXT_ROWS", "50"))

_COMMENT_BLOCK_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_COMMENT_LINE_RE = re.compile(r"--[^\n]*")
_FORBIDDEN_KEYWORDS = re.compile(
    r"\b(insert|update|delete|drop|alter|truncate|create|grant|revoke|merge|call|execute)\b",
    re.IGNORECASE,
)


def _json_default(val: Any) -> Any:
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, (datetime, date)):
        return val.isoformat()
    if isinstance(val, bytes):
        return val.decode("utf-8", errors="replace")
    return str(val)


def validate_readonly_sql(sql: str) -> str | None:
    """Returns None if SQL is a safe single-statement SELECT/WITH, else error message."""
    no_comments = _COMMENT_LINE_RE.sub(" ", _COMMENT_BLOCK_RE.sub(" ", sql or ""))
    cleaned = no_comments.strip().rstrip(";").strip()
    if not cleaned:
        return "Empty SQL query."
    if ";" in cleaned:
        return "Multi-statement SQL queries are prohibited."
    first_token = cleaned.split(None, 1)[0].lower()
    if first_token not in ("select", "with"):
        return f"Only read-only SELECT/WITH queries are allowed (got '{first_token}')."
    if _FORBIDDEN_KEYWORDS.search(cleaned):
        return "Disallowed DML/DDL keyword detected in query."
    return None


def _execute_guarded_bigquery(sql: str, max_scan_mb: float | None = None) -> Dict[str, Any]:
    """Runs dry_run byte check followed by row-capped BigQuery execution."""
    project_id = os.environ.get("BQ_PROJECT_ID") or None
    client = bigquery.Client(project=project_id)
    default_ds = f"{client.project}.{DEFAULT_DATASET}"

    effective_cap_bytes = (
        int(max_scan_mb * 1024 * 1024) if max_scan_mb is not None else MAX_SCAN_BYTES
    )

    # 1. Mandatory Pre-Execution Dry Run
    dry_config = bigquery.QueryJobConfig(
        default_dataset=default_ds,
        dry_run=True,
        use_query_cache=True,
    )
    dry_job = client.query(sql, job_config=dry_config)
    est_bytes = int(dry_job.total_bytes_processed or 0)
    est_mb = round(est_bytes / (1024 * 1024), 2)
    cap_mb = round(effective_cap_bytes / (1024 * 1024), 2)

    if est_bytes > effective_cap_bytes:
        return {
            "status": "blocked_by_dry_run_budget",
            "estimated_mb_scanned": est_mb,
            "budget_mb_limit": cap_mb,
            "guidance": (
                f"Query blocked before execution: estimated scan ({est_mb} MB) "
                f"exceeds safety budget ({cap_mb} MB). Add partition/WHERE filters "
                "or select only required columns."
            ),
        }

    # 2. Bounded Execution with Hard Context-Window Row Cap
    exec_config = bigquery.QueryJobConfig(
        default_dataset=default_ds,
        maximum_bytes_billed=effective_cap_bytes,
        use_query_cache=True,
    )
    query_job = client.query(sql, job_config=exec_config)
    row_iter = query_job.result(max_results=MAX_CONTEXT_ROWS)
    rows = [dict(r) for r in row_iter]
    total_rows = int(row_iter.total_rows or len(rows))
    truncated = total_rows > MAX_CONTEXT_ROWS

    payload: Dict[str, Any] = {
        "status": "ok",
        "estimated_mb_scanned": est_mb,
        "total_rows_matched": total_rows,
        "rows_returned": len(rows),
        "truncated_for_context_window": truncated,
        "rows": rows,
    }
    if truncated:
        payload["guidance"] = (
            f"Showing first {MAX_CONTEXT_ROWS} of {total_rows:,} matched rows to "
            "protect the LLM context window. Push GROUP BY / COUNT / SUM / AVG "
            "aggregations or tighter WHERE predicates into SQL."
        )
    return payload


@mcp_server.list_tools()
async def list_tools() -> List[types.Tool]:
    schema = (
        "- app_events (event_id STRING, customer_email STRING, event_type STRING, "
        "device_os STRING, timestamp TIMESTAMP, payload STRING) [16M+ rows]\n"
        "- customer_risk_profiles (customer_email STRING, churn_risk_score FLOAT64, "
        "fraud_risk_score FLOAT64, last_calculated TIMESTAMP) [50M+ rows]"
    )
    return [
        types.Tool(
            name="query_bigquery_v2",
            description=(
                f"Execute a guardrailed read-only GoogleSQL SELECT query on BigQuery "
                f"dataset '{DEFAULT_DATASET}' (pre-validated with dry_run byte budget "
                f"and capped at {MAX_CONTEXT_ROWS} returned rows). Schema:\n{schema}"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Single-statement GoogleSQL SELECT query. Prefer SQL "
                            "aggregations (COUNT, SUM, AVG, GROUP BY) and LIMIT."
                        ),
                    },
                    "max_scan_mb": {
                        "type": "number",
                        "description": (
                            "Optional per-query scan budget override in MiB "
                            "(defaults to server BQ_MAX_SCAN_BYTES)."
                        ),
                    },
                },
                "required": ["query"],
            },
        )
    ]


@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict) -> List[types.TextContent]:
    if name != "query_bigquery_v2":
        raise ValueError(f"Unknown tool: {name}")

    args = arguments or {}
    query = args.get("query", "")
    max_scan_mb = args.get("max_scan_mb")

    err = validate_readonly_sql(query)
    if err:
        return [
            types.TextContent(
                type="text",
                text=json.dumps({"status": "rejected_by_sql_guardrail", "error": err}),
            )
        ]

    try:
        result = await asyncio.to_thread(_execute_guarded_bigquery, query, max_scan_mb)
    except Exception as exc:
        logger.error("BigQuery v2 execution error: %s", exc)
        result = {"status": "error", "error": str(exc)}

    return [
        types.TextContent(
            type="text",
            text=json.dumps(result, default=_json_default, separators=(",", ":")),
        )
    ]


transport = StreamableHTTPServerTransport(
    mcp_session_id=None, is_json_response_enabled=True
)


async def healthz(_request):
    return JSONResponse({"status": "healthy", "service": "mcp-server-bigquery-v2"})


@asynccontextmanager
async def lifespan(_app_instance: Starlette):
    async def run_mcp():
        async with transport.connect() as (read_stream, write_stream):
            await mcp_server.run(
                read_stream,
                write_stream,
                mcp_server.create_initialization_options(),
            )

    mcp_task = asyncio.create_task(run_mcp())
    yield
    mcp_task.cancel()


starlette_app = Starlette(routes=[Route("/healthz", healthz)], lifespan=lifespan)


async def app(scope: Scope, receive: Receive, send: Send) -> None:
    if scope["type"] == "http" and scope["path"] in ("/mcp", "/mcp/", "/sse", "/sse/"):
        await transport.handle_request(scope, receive, send)
        return
    await starlette_app(scope, receive, send)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    host = os.environ.get("HOST", "0.0.0.0")
    uvicorn.run(app, host=host, port=port)
