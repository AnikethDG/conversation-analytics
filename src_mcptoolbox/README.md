# Cross-Cloud Conversational Analytics — Google MCP Toolbox Architecture (`src_mcptoolbox/`)

Production-oriented **v2** implementation of **Zero-Copy Cross-Cloud Conversational Analytics** powered by **Google's official [MCP Toolbox for Databases](https://github.com/googleapis/genai-toolbox)** (`genai-toolbox` `v1.1.0`), paired with a **Guardrailed BigQuery MCP Server** and the **`Sentinel — Customer 360 & Risk Advisor_v2`** agent on **Vertex AI Agent Engine (`google-adk`)** and **Gemini Enterprise**.

> **Side-by-Side Isolation**: Everything in `src_mcptoolbox/` deploys with `_v2` / `-v2` suffixes and `poc_version=v2` resource labels so it runs cleanly alongside the original custom Python prototype in [`../src/`](../src) and can be torn down in a single command via [`scripts_v2/teardown_v2.sh`](./scripts_v2/teardown_v2.sh).

---

## 1. Architecture Overview

```text
  [ Business User — Gemini Enterprise / Vertex AI Playground ]
                                │
                                ▼
  ╔═══════════════════════════════════════════════════════════════════════╗
  ║  Vertex AI Agent Engine: Sentinel — Customer 360 & Risk Advisor_v2    ║
  ║  • Framework : google-adk (gemini-2.5-flash) + OpenTelemetry Trace    ║
  ║  • Auth      : CloudRunOIDCMcpToolset (auto-rotating OIDC ID tokens)  ║
  ╚══════════════════════╤════════════════════════════════╤═══════════════╝
                         │ OIDC Bearer (mTLS/HTTPS)       │ OIDC Bearer (mTLS/HTTPS)
                         ▼                                ▼
  ┌─────────────────────────────────────────┐   ┌──────────────────────────────────────┐
  │ Cloud Run: mcp-toolbox-databases-v2     │   │ Cloud Run: mcp-server-bigquery-v2    │
  │ • Image: Google Official MCP Toolbox    │   │ • Pre-flight BigQuery dry_run check  │
  │ • Config: tools_v2.yaml (Secret Mgr)    │   │ • Hard 50-row context-window cap     │
  │ • Go-native connection pooling          │   │ • Comment-stripped SELECT validator  │
  │ • 10 parameterized tools ($1 / ? / @)   │   │ • Ad-hoc GoogleSQL fallback          │
  └──────┬──────────────────┬───────────────┘   └──────────────────┬───────────────────┘
         │ Pooled TCP 5432  │ Pooled TCP 3306                      │ Native BQ Slots
         ▼                  ▼                                      ▼
  ┌──────────────┐   ┌──────────────┐                     ┌────────────────────────────┐
  │ AWS Postgres │   │  AWS MySQL   │                     │  GCP BigQuery (`ccca`)     │
  │ `finance_db` │   │`engagement_db│                     │  • 50M risk profiles       │
  │ 2M customers │   │  1M tickets  │                     │  • 16M app telemetry rows  │
  └──────────────┘   └──────────────┘                     └────────────────────────────┘
```

---

## 2. Why `MCP Toolbox` (`src_mcptoolbox/`) Beats Custom MCP Servers (`src/`)

| Engineering Dimension | v1 Custom Python MCP ([`../src/`](../src)) | v2 Google `MCP Toolbox` + Guardrails (`src_mcptoolbox/`) |
| :--- | :--- | :--- |
| **Server Code & Maintenance** | ~550 lines of custom Python (`Starlette`, `uvicorn`, custom `/sse` ASGI router, manual `mcp==1.29.0` SDK pinning) across 3 Dockerfiles | **Zero custom server code** for operational DBs — runs Google's prebuilt Go container (`database-toolbox/toolbox`) configured via declarative [`tools_v2.yaml`](./mcp_toolbox_v2/tools_v2.yaml) |
| **Database Connection Management** | Opens & closes a brand-new `psycopg2.connect()` / `pymysql.connect()` TCP + auth handshake on **every tool call** (risks connection exhaustion under concurrency) | **Built-in Go-native connection pooling** reused across concurrent agent invocations |
| **SQL Injection & Query Safety** | LLM writes raw SQL strings checked only by prefix (`startswith("select")`) | **100% parameterized SQL statements** (`$1` in Postgres, `?` in MySQL, `@param` in BigQuery) — user/LLM inputs are bound as typed data parameters, never concatenated into SQL syntax |
| **Cross-Cloud Join Efficiency** | Prone to sequential N+1 tool calls or fragile LLM-authored `IN (...)` strings | Dedicated **single-round-trip batch tools** (`ANY(string_to_array($1, ','))`, `FIND_IN_SET(?, ...)`, `UNNEST(SPLIT(@emails_csv, ','))`) correlating up to 50 entities in 1 call per DB |
| **Context-Window Protection** | Missing a `LIMIT` on a 50M-row table attempts `[dict(row) for row in results]`, crashing Cloud Run or overflowing Gemini's context window | Curated tools enforce strict SQL `LIMIT`s (`5`–`50` rows) & SQL-side `GROUP BY`, while [`main_v2.py`](./mcp_bigquery_v2/main_v2.py) enforces `max_results=50` pagination + truncation guidance |
| **BigQuery FinOps Cost Control** | Executes whatever `SELECT` the LLM emits with no pre-execution check | Mandatory **`dry_run=True` pre-flight check** blocks over-budget scans (`0 bytes billed`) before execution |
| **Wire Serialization & Tokens** | Python `str(results)` emits `RealDictRow([('balance', Decimal('...'))])` (~35% wasted tokens) | Clean, standard JSON arrays/floats (`4,806`–`7,220` total tokens across full 3-database multi-turn reasoning) |
| **Cloud Run Ingress & Secrets** | Originally `--allow-unauthenticated` with plain-text env vars | `--no-allow-unauthenticated` (`HTTP 403` to unauthenticated callers), Secret Manager mounts (`ccca_*_v2`), and auto-rotating OIDC ID tokens in [`CloudRunOIDCMcpToolset`](./sentinel_customer_360_advisor_v2/agent.py) |

### Pros & Cons Summary

* **Google `MCP Toolbox` (`tools_v2.yaml`)**:
  * **Pros**: Zero Python driver boilerplate; native connection pooling; immune to SQL injection via prepared parameters; deterministic query plans reviewed by DBAs; built-in OpenTelemetry/Cloud Monitoring (`--telemetry-gcp`); hot-swappable YAML config via Secret Manager without rebuilding Docker images.
  * **Cons / Trade-off**: Purely fixed SQL templates cannot anticipate every brand-new ad-hoc analytical slice an executive might ask on a warehouse.
  * **How `src_mcptoolbox/` Solves That Trade-off**: We use **MCP Toolbox** for 100% of operational OLTP queries (`AWS Postgres` & `AWS MySQL`) + common `BigQuery` 360/cohort paths, and pair it with **`mcp-server-bigquery-v2`** (`dry_run` + `50`-row cap) exclusively for open-ended read-only warehouse exploration.

---

## 3. Directory Structure

```text
src_mcptoolbox/
├── README.md                                  # Architecture, v1-vs-v2 comparison & setup guide
├── mcp_toolbox_v2/
│   └── tools_v2.yaml                          # Declarative Google MCP Toolbox config (3 sources, 10 tools)
├── mcp_bigquery_v2/
│   ├── Dockerfile                             # Container spec for guardrailed ad-hoc BigQuery MCP
│   ├── .gcloudignore
│   ├── main_v2.py                             # dry_run byte budget + 50-row context guard + JSON output
│   └── requirements_v2.txt
├── sentinel_customer_360_advisor_v2/          # Deployable Vertex AI Agent Engine package (google-adk)
│   ├── __init__.py
│   ├── agent.py                               # root_agent + CloudRunOIDCMcpToolset (45-min OIDC cache)
│   ├── prompt_v2.md                           # Enterprise persona & cardinality-aware tool routing
│   ├── requirements.txt
│   └── .env.example
├── agent_v2/                                  # Standalone local ADK evaluation runner
│   ├── agent_v2.py
│   ├── prompt_v2.md
│   └── requirements_v2.txt
├── tests_v2/
│   └── benchmark_v2.py                        # Automated 4-stage security, scale & ADK benchmark suite
└── scripts_v2/
    ├── deploy_v2.sh                           # Deploys Secret Manager, IAM SA & both _v2 Cloud Run services
    └── teardown_v2.sh                         # 1-command cleanup of ALL _v2 resources (leaves v1 intact)
```

---

## 4. Curated Tool Catalog in [`tools_v2.yaml`](./mcp_toolbox_v2/tools_v2.yaml)

| Tool Name | Engine | Purpose |
| :--- | :--- | :--- |
| `pg_get_customer_360_v2` | AWS PostgreSQL | CTE-optimized customer lookup returning accounts, balances & transaction rollups |
| `pg_batch_accounts_by_emails_v2` | AWS PostgreSQL | Single-round-trip `ANY(string_to_array($1, ','))` batch account lookup (up to 50 emails) |
| `pg_top_customers_by_balance_v2` | AWS PostgreSQL | Top/bottom accounts by balance & type (`checking`, `savings`, `credit`, `all`), capped ≤25 |
| `pg_ledger_summary_kpis_v2` | AWS PostgreSQL | In-database `COUNT` / `SUM` / `AVG` rollup across 4M+ accounts (returns 3 summary rows) |
| `mysql_get_customer_engagement_v2` | AWS MySQL | Parameterized lookup of a customer's support tickets & marketing campaign responses |
| `mysql_batch_engagement_by_emails_v2` | AWS MySQL | Batched `FIND_IN_SET` lookup of tickets & campaigns for up to 50 emails in 1 call |
| `mysql_engagement_summary_kpis_v2` | AWS MySQL | Aggregated ticket counts by status & campaign conversion breakdown across 1M+ rows |
| `bq_get_customer_risk_and_events_v2` | GCP BigQuery | De-correlated CTE lookup of `fraud_risk_score`, `churn_risk_score` & 5 recent app events |
| `bq_batch_risk_by_emails_v2` | GCP BigQuery | Batched `UNNEST(SPLIT(@emails_csv, ','))` risk + crash event lookup for up to 50 emails |
| `bq_top_risk_cohort_v2` | GCP BigQuery | Prunes 50M `customer_risk_profiles` rows inside BigQuery slots to top 10 high-risk emails |
| `query_bigquery_v2` *(fallback)* | GCP BigQuery | Ad-hoc GoogleSQL `SELECT` protected by `dry_run` byte caps & `50`-row truncation |

---

## 5. Deploy, Verify & Tear Down

### Step 1: Deploy `_v2` Cloud Run MCP Stack

```bash
export PROJECT_ID="<YOUR_GCP_PROJECT_ID>"
export REGION="us-west1"
export POSTGRES_HOST="<AWS_POSTGRES_HOST>" POSTGRES_USER="postgres" POSTGRES_PASSWORD="<SECRET>"
export MYSQL_HOST="<AWS_MYSQL_HOST>"       MYSQL_USER="admin"       MYSQL_PASSWORD="<SECRET>"

./src_mcptoolbox/scripts_v2/deploy_v2.sh
```

### Step 2: Deploy `Sentinel — Customer 360 & Risk Advisor_v2` to Vertex AI Agent Engine

```bash
adk deploy agent_engine \
  --project="${PROJECT_ID}" \
  --region="${REGION}" \
  --display_name="Sentinel — Customer 360 & Risk Advisor_v2" \
  --service_account="ccca-agent-caller-v2@${PROJECT_ID}.iam.gserviceaccount.com" \
  --otel_to_cloud \
  ./src_mcptoolbox/sentinel_customer_360_advisor_v2
```

### Step 3: Run the Live Verification & Benchmark Suite

```bash
PROJECT_ID="${PROJECT_ID}" \
TOOLBOX_V2_BASE_URL="https://mcp-toolbox-databases-v2-<hash>-uw.a.run.app" \
BQ_V2_BASE_URL="https://mcp-server-bigquery-v2-<hash>-uw.a.run.app" \
python3 ./src_mcptoolbox/tests_v2/benchmark_v2.py
```

### Step 4: 1-Command Teardown (`_v2` Only)

```bash
PROJECT_ID="${PROJECT_ID}" ./src_mcptoolbox/scripts_v2/teardown_v2.sh
```
