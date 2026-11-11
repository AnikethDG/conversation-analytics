# MCP Cloud Run Engineering Notes

Hosting Model Context Protocol (MCP) database servers on serverless platforms like **Google Cloud Run** requires specific transport, concurrency, and safety patterns:

## 1. Non-Blocking Database I/O (`asyncio.to_thread`)
Synchronous database drivers (`psycopg2`, `pymysql`, `google-cloud-bigquery`) block the main Python thread if called directly inside an `async def` handler, starving Cloud Run health checks and concurrent requests. All three MCP servers offload driver execution via `await asyncio.to_thread(...)` so the Starlette `asyncio` loop stays responsive.

## 2. Deterministic SDK Pinning (`mcp==1.29.0`)
All three MCP services pin `mcp==1.29.0` in `requirements.txt` so automated Cloud Build deployments remain immune to breaking decorator/transport changes in newer major SDK versions.

## 3. Stateless JSON-RPC Over HTTP (`StreamableHTTPServerTransport`)
Managed agent orchestrators (Vertex AI Agent Engine / Gemini Enterprise) issue stateless JSON-RPC `POST` requests directly without maintaining sticky Server-Sent Events (SSE) session query parameters. Each server configures:
```python
transport = StreamableHTTPServerTransport(
    mcp_session_id=None, is_json_response_enabled=True
)
```
and intercepts `/sse`, `/sse/`, `/mcp`, and `/mcp/` directly in a thin ASGI wrapper to avoid `307 Temporary Redirect` responses on trailing slashes.

## 4. Defense-in-Depth Read-Only Enforcement
Each server enforces read-only execution at two levels:
1. **MCP Input Validator**: `_is_safe_select()` rejects empty queries, multi-statement semicolons (`;`), and any SQL statement whose leading verb is outside `SELECT` / `WITH`.
2. **Database Engine Guardrails**:
   - **PostgreSQL**: Sets `-c default_transaction_read_only=on -c statement_timeout=5000` at connection startup.
   - **MySQL**: Executes `SET SESSION TRANSACTION READ ONLY;` with a 5-second `read_timeout`.
   - **BigQuery**: Enforces `maximum_bytes_billed` (`10 GB` default) via `QueryJobConfig`.
