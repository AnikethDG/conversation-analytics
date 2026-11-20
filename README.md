# Cross-Cloud Conversational Analytics

Zero-copy **Cross-Cloud Conversational Analytics** across **AWS** operational databases (`PostgreSQL`, `MySQL`) and **Google Cloud BigQuery** (`66.0M+` rows) powered by **Vertex AI Agent Engine (`google-adk`)**, **Gemini Enterprise**, and **Google's [MCP Toolbox for Databases](https://github.com/googleapis/genai-toolbox)** on **Google Cloud Run**.

---

## Repository Structure

| Directory | Description | Status |
| :--- | :--- | :--- |
| **[`src_v3_native_bq/`](./src_v3_native_bq)** | **Zero-Custom-Server v3 Architecture (`MCP Toolbox` + Native BigQuery MCP)**: Pairs Google `MCP Toolbox` (AWS Postgres & MySQL) with Google's managed **`https://bigquery.googleapis.com/mcp`** endpoint (read-only `tool_filter` + dataset-scoped IAM)—eliminating all custom MCP Dockerfiles. | **Latest (`v3` Zero Custom Containers)** |
| **[`src_mcptoolbox/`](./src_mcptoolbox)** | **Enterprise v2 Architecture (Google `MCP Toolbox` + Guardrails)**: Official prebuilt `genai-toolbox` (`v1.1.0`) configured via declarative [`tools_v2.yaml`](./src_mcptoolbox/mcp_toolbox_v2/tools_v2.yaml), paired with a `dry_run` + `50`-row-capped BigQuery MCP server and **`Sentinel — Customer 360 & Risk Advisor_v2`** on Vertex AI Agent Engine. | **Recommended (Custom `dry_run` Cap)** |
| **[`src/`](./src)** | **Baseline v1 Prototype (Custom Python MCP Servers)**: Three custom Python/Starlette containers (`psycopg2`, `pymysql`, `google-cloud-bigquery`) executing raw LLM-generated `SELECT` SQL strings. | Reference Baseline |
| **[`doc/`](./doc)** | **Interactive Google Cloud Executive Brief & 5-Slide Pitch Portal**: Visual `< Prev` / `Next >` multi-hop flow walkthrough (`User ↔ Analytics Agent ↔ Cloud Run MCP ↔ AWS Postgres, AWS MySQL & GCP BigQuery`) and 5-slide executive presentation. | Web Portal |

---

## Why We Upgraded from Custom MCP (`src/`) to Google `MCP Toolbox` (`src_mcptoolbox/`)

In our initial prototype ([`src/`](./src)), we built three bespoke Python MCP servers that accepted raw SQL strings from the LLM and opened a new database connection on every call. While effective for proving cross-cloud connectivity, testing against enterprise-scale datasets (**`2.0M` AWS PostgreSQL customers / `4.0M` accounts**, **`1.0M` AWS MySQL support tickets**, and **`50.0M` BigQuery ML risk profiles + `16.0M` app events**) exposed critical bottlenecks in connection management, context-window safety, and SQL governance.

In [`src_mcptoolbox/`](./src_mcptoolbox), we replaced custom operational database wrappers with **Google's official `MCP Toolbox for Databases`** (`us-central1-docker.pkg.dev/database-toolbox/toolbox/toolbox`) and added pre-execution warehouse guardrails.

### Key Differences: Custom Python MCP (`v1`) vs. Google `MCP Toolbox` (`v2`)

| Capability | Custom Python MCP ([`src/`](./src)) | Google `MCP Toolbox` + Guardrails ([`src_mcptoolbox/`](./src_mcptoolbox)) |
| :--- | :--- | :--- |
| **Implementation Footprint** | 3 custom Python microservices (~550 LOC), custom `/sse` ASGI routing workarounds, and manual `mcp==1.29.0` version pinning | **0 lines of custom DB wrapper code** for Postgres/MySQL — declarative [`tools_v2.yaml`](./src_mcptoolbox/mcp_toolbox_v2/tools_v2.yaml) mounted directly into Google's official Go container |
| **Connection Pooling** | **None** — opens & closes a new TCP/auth connection per tool call (`psycopg2.connect` / `pymysql.connect`), risking OLTP connection exhaustion under load | **Built-in Go connection pooling** shared cleanly across concurrent requests |
| **SQL Injection & DBA Safety** | LLM generates raw SQL text validated only by prefix (`SELECT`) | **Typed parameterized statements** (`$1`, `?`, `@param`) — inputs are bound at the protocol level and query plans are pre-vetted |
| **Cross-Cloud Joins (N+1 Problem)** | Relies on prompt discipline to avoid N+1 per-customer loops | Explicit **batched array/CSV tools** (`pg_batch_accounts_by_emails_v2`, `mysql_batch_engagement_by_emails_v2`, `bq_batch_risk_by_emails_v2`) joining up to 50 entities in **1 round-trip per DB** |
| **LLM Context-Window Protection** | Unbounded `[dict(row) for row in results]` — a forgotten `LIMIT` on a 50M-row table OOMs Cloud Run or overflows Gemini's context window | SQL-enforced `LIMIT`s & aggregations in `tools_v2.yaml` + hard **`max_results=50` row cap** with truncation metadata in [`main_v2.py`](./src_mcptoolbox/mcp_bigquery_v2/main_v2.py) |
| **BigQuery FinOps Protection** | No pre-flight cost check | Mandatory **`dry_run=True` byte budget check** blocks over-budget scans (`0 bytes billed`) before execution |
| **Payload & Token Efficiency** | Python `str(results)` serializes `RealDictRow` / `Decimal(...)` reprs (~35% token overhead) | Compact native JSON (`~4.8K–7.2K` total LLM tokens across complete 3-database multi-turn reasoning) |
| **Authentication & Secrets** | Originally `--allow-unauthenticated` + env-var credentials | `--no-allow-unauthenticated` Cloud Run IAM (`HTTP 403` to public callers), Secret Manager mounts, and auto-rotating OIDC ID tokens in [`CloudRunOIDCMcpToolset`](./src_mcptoolbox/sentinel_customer_360_advisor_v2/agent.py) |

---

## Pros & Cons: `MCP Toolbox` vs. Custom MCP Servers

### 1. Google `MCP Toolbox for Databases` ([`src_mcptoolbox/`](./src_mcptoolbox))
* **Pros**:
  * **Production OLTP Stability**: Native connection pooling prevents connection storms against AWS PostgreSQL and MySQL instances.
  * **Zero SQL-Injection Surface**: LLMs pass structured arguments (`email`, `min_fraud_score`, `emails_csv`) into pre-compiled SQL statements rather than synthesizing arbitrary SQL against operational tables.
  * **Zero Transport Maintenance**: Protocol upgrades (Streamable HTTP, session handling, OpenTelemetry metrics via `--telemetry-gcp`) are maintained upstream by Google.
  * **Instant Config Rollouts**: Adding or tuning a tool only updates `tools_v2.yaml` in Secret Manager—no container rebuild required.
* **Cons**:
  * **Less Flexible for Unplanned Ad-Hoc Queries**: Purely declarative SQL templates require pre-defining query shapes, which can be restrictive when analysts ask novel exploratory slicing questions on a data warehouse.
* **Architectural Mitigation in `src_mcptoolbox/`**:
  * We combine **both strengths**: `MCP Toolbox` handles **100% of operational AWS OLTP traffic** + high-frequency BigQuery 360/cohort lookups, while a lightweight **Guardrailed BigQuery MCP server** (`mcp-server-bigquery-v2`) handles open-ended warehouse `SELECT` queries behind a mandatory `dry_run` byte cap and `50`-row context-window ceiling.

### 2. Custom Python MCP Servers ([`src/`](./src))
* **Pros**:
  * **Maximum Ad-Hoc Flexibility**: The LLM can write arbitrary `JOIN`s or `GROUP BY`s on the fly, and engineers can embed custom Python post-processing logic directly inside tool handlers.
* **Cons**:
  * **Poor Scalability**: Per-request synchronous connections, lack of pooling, and unbounded result sets fail quickly as table sizes (`50M+` rows) or concurrent users grow.
  * **Higher Security & Maintenance Burden**: Teams must maintain custom ASGI transport code, SDK version pins, SQL parsers, and container builds for every database dialect.

---

## How `src_mcptoolbox/` Scales in Enterprise Deployments

1. **Warehouse-First Cohort Pushdown**: `50M`-row filtering and `4M`-account KPI aggregations execute inside BigQuery slots and Postgres/MySQL engines—never inside LLM memory.
2. **Bounded Context Payloads (`≤ 5 KB`)**: Even if a user or model omits `LIMIT` on a `50,000,055`-row table, `mcp-server-bigquery-v2` streams only the first `50` rows (`4,533 bytes` in live benchmarks) with `truncated_for_context_window: true`, guaranteeing predictable latency and token cost.
3. **Stateless Horizontal Autoscaling on Cloud Run**: Both `mcp-toolbox-databases-v2` and `mcp-server-bigquery-v2` use stateless JSON-RPC over `/mcp`, allowing Cloud Run instances to autoscale horizontally while `MCP Toolbox` bounds per-instance database pool connections.
4. **Dynamic OIDC Workload Identity**: [`Sentinel — Customer 360 & Risk Advisor_v2`](./src_mcptoolbox/sentinel_customer_360_advisor_v2/agent.py) runs under a dedicated least-privilege service account and refreshes Google-signed OIDC tokens automatically every 45 minutes—eliminating static keys and public endpoints.

---

## Quick Start

### 1. Deploy the `MCP Toolbox` v2 Stack & `Sentinel` Agent
See **[`src_mcptoolbox/README.md`](./src_mcptoolbox/README.md)** for full deployment, live benchmark, and 1-command teardown instructions:

```bash
export PROJECT_ID="<YOUR_GCP_PROJECT_ID>"
export REGION="us-west1"
export POSTGRES_HOST="<AWS_POSTGRES_HOST>" POSTGRES_USER="postgres" POSTGRES_PASSWORD="<SECRET>"
export MYSQL_HOST="<AWS_MYSQL_HOST>"       MYSQL_USER="admin"       MYSQL_PASSWORD="<SECRET>"

./src_mcptoolbox/scripts_v2/deploy_v2.sh
```

### 2. Launch the Interactive Executive Brief & 5-Slide Pitch Portal Locally

```bash
python3 -m http.server 8999 --bind 127.0.0.1 --directory ./doc
```

Open `http://127.0.0.1:8999/` in your browser.
