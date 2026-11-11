"""MCP Server for Cross-Cloud Conversational Analytics (BigQuery Bridge).

Implements a Cloud Run compatible Model Context Protocol (MCP) server exposing
read-only GoogleSQL access to BigQuery dataset `ccca` with configurable
maximum_bytes_billed cost guardrails.
"""

import asyncio
from contextlib import asynccontextmanager
import logging
import os
from typing import List, Union

from google.cloud import bigquery
import mcp.types as types
from mcp.server import Server
from mcp.server.streamable_http import StreamableHTTPServerTransport
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.types import Receive, Scope, Send
import uvicorn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

mcp_server = Server("Gemini-BigQuery-MCP-Bridge")

DEFAULT_DATASET = os.environ.get("BQ_DATASET", "ccca")
MAX_BYTES_BILLED = int(os.environ.get("BQ_MAX_BYTES_BILLED", str(10 * 1024**3)))


def _is_safe_select(sql: str) -> bool:
    """Validates that the SQL statement is a single read-only SELECT/WITH query."""
    cleaned = sql.strip().rstrip(";").strip()
    if not cleaned or ";" in cleaned:
        return False
    first_token = cleaned.split(None, 1)[0].lower()
    return first_token in ("select", "with")


def _query_bigquery(sql: str) -> Union[List[dict], str]:
    """Executes a read-only GoogleSQL query on BigQuery with scan caps."""
    try:
        project_id = os.environ.get("BQ_PROJECT_ID") or None
        client = bigquery.Client(project=project_id)
        job_config = bigquery.QueryJobConfig(
            default_dataset=f"{client.project}.{DEFAULT_DATASET}",
            maximum_bytes_billed=MAX_BYTES_BILLED,
        )
        query_job = client.query(sql, job_config=job_config)
        results = query_job.result()
        return [dict(row) for row in results]
    except Exception as exc:
        logger.error("BigQuery query failed: %s", exc)
        return f"BigQuery Error: {exc}"


@mcp_server.list_tools()
async def list_tools() -> List[types.Tool]:
    """Lists available tools and table schemas exposed by this MCP server."""
    schema = (
        "- app_events (event_id, customer_email, event_type, device_os, timestamp, payload)\n"
        "- customer_risk_profiles (customer_email, churn_risk_score, fraud_risk_score, last_calculated)"
    )
    return [
        types.Tool(
            name="query_bigquery",
            description=(
                f"Execute a read-only GoogleSQL SELECT query on BigQuery dataset "
                f"'{DEFAULT_DATASET}'. Schema:\n{schema}"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Read-only GoogleSQL SELECT query to execute.",
                    }
                },
                "required": ["query"],
            },
        )
    ]


@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict) -> List[types.TextContent]:
    """Handles MCP tool execution calls."""
    if name != "query_bigquery":
        raise ValueError(f"Unknown tool: {name}")

    query = (arguments or {}).get("query", "")
    if not query:
        return [types.TextContent(type="text", text="Error: Missing query argument.")]
    if not _is_safe_select(query):
        return [
            types.TextContent(
                type="text",
                text="Error: Only single-statement read-only SELECT queries are allowed.",
            )
        ]

    results = await asyncio.to_thread(_query_bigquery, query)
    return [types.TextContent(type="text", text=str(results))]


transport = StreamableHTTPServerTransport(
    mcp_session_id=None, is_json_response_enabled=True
)


@asynccontextmanager
async def lifespan(app_instance: Starlette):
    """Performs startup connectivity check and runs the MCP server loop."""
    logger.info("Checking BigQuery connectivity...")
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(_query_bigquery, "SELECT 1 AS ok"), timeout=5.0
        )
        logger.info("BigQuery connectivity check result: %s", result)
    except Exception as exc:
        logger.warning("BigQuery startup check warning: %s", exc)

    async def run_mcp():
        try:
            async with transport.connect() as (read_stream, write_stream):
                await mcp_server.run(
                    read_stream,
                    write_stream,
                    mcp_server.create_initialization_options(),
                )
        except Exception as exc:
            logger.error("MCP server loop error: %s", exc)

    mcp_task = asyncio.create_task(run_mcp())
    yield
    mcp_task.cancel()


starlette_app = Starlette(routes=[], lifespan=lifespan)
allowed_origins = [
    o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()
]
if allowed_origins:
    starlette_app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_methods=["POST", "GET", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )


async def app(scope: Scope, receive: Receive, send: Send) -> None:
    """ASGI router handling stateless /sse and /mcp requests without 307 redirects."""
    if scope["type"] == "http" and scope["path"] in ("/sse", "/sse/", "/mcp", "/mcp/"):
        await transport.handle_request(scope, receive, send)
        return
    await starlette_app(scope, receive, send)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    host = os.environ.get("HOST", "0.0.0.0")
    uvicorn.run(app, host=host, port=port)
