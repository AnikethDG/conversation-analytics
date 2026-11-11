"""MCP Server for Cross-Cloud Conversational Analytics (PostgreSQL Bridge).

Implements a Cloud Run compatible Model Context Protocol (MCP) server exposing
read-only SQL access to an operational PostgreSQL database (e.g., AWS RDS/EC2).
Uses StreamableHTTPServerTransport for stateless JSON-RPC HTTP POST requests.
"""

import asyncio
from contextlib import asynccontextmanager
import logging
import os
from typing import List, Union

import mcp.types as types
from mcp.server import Server
from mcp.server.streamable_http import StreamableHTTPServerTransport
import psycopg2
from psycopg2.extras import RealDictCursor
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.types import Receive, Scope, Send
import uvicorn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

mcp_server = Server("Gemini-Postgres-MCP-Bridge")


def _is_safe_select(sql: str) -> bool:
    """Validates that the SQL statement is a single read-only SELECT/WITH query."""
    cleaned = sql.strip().rstrip(";").strip()
    if not cleaned or ";" in cleaned:
        return False
    first_token = cleaned.split(None, 1)[0].lower()
    return first_token in ("select", "with")


def _query_postgres(sql: str) -> Union[List[dict], str]:
    """Executes a read-only SQL query on the PostgreSQL database."""
    conn = None
    try:
        conn = psycopg2.connect(
            host=os.environ["POSTGRES_HOST"],
            port=int(os.environ.get("POSTGRES_PORT", "5432")),
            database=os.environ["POSTGRES_DB"],
            user=os.environ["POSTGRES_USER"],
            password=os.environ["POSTGRES_PASSWORD"],
            connect_timeout=5,
            options="-c default_transaction_read_only=on -c statement_timeout=5000",
        )
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql)
            return [dict(row) for row in cur.fetchall()]
    except Exception as exc:
        logger.error("PostgreSQL query failed: %s", exc)
        return f"PostgreSQL Error: {exc}"
    finally:
        if conn:
            conn.close()


@mcp_server.list_tools()
async def list_tools() -> List[types.Tool]:
    """Lists available tools and table schemas exposed by this MCP server."""
    schema = (
        "- customers (id, name, email)\n"
        "- accounts (id, customer_id, type, balance)\n"
        "- transactions (id, account_id, amount, date)"
    )
    return [
        types.Tool(
            name="query_postgres",
            description=(
                "Execute a read-only SQL SELECT query on PostgreSQL database "
                f"'finance_db'. Schema:\n{schema}"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Read-only SQL SELECT query to execute.",
                    }
                },
                "required": ["query"],
            },
        )
    ]


@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict) -> List[types.TextContent]:
    """Handles MCP tool execution calls."""
    if name != "query_postgres":
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

    results = await asyncio.to_thread(_query_postgres, query)
    return [types.TextContent(type="text", text=str(results))]


transport = StreamableHTTPServerTransport(
    mcp_session_id=None, is_json_response_enabled=True
)


@asynccontextmanager
async def lifespan(app_instance: Starlette):
    """Performs startup connectivity check and runs the MCP server loop."""
    logger.info("Checking PostgreSQL connectivity...")
    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(_query_postgres, "SELECT 1 AS ok"), timeout=5.0
        )
        logger.info("PostgreSQL connectivity check result: %s", result)
    except Exception as exc:
        logger.warning("PostgreSQL startup check warning: %s", exc)

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
