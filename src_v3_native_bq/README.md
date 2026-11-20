# Cross-Cloud Conversational Analytics — `v3` Native BigQuery MCP Architecture (`src_v3_native_bq/`)

Zero-custom-container **v3** evolution of Cross-Cloud Conversational Analytics that **eliminates `mcp-server-bigquery-v2`** altogether by connecting **`Sentinel — Customer 360 & Risk Advisor_v3`** directly to **Google's native managed remote BigQuery MCP server** (`https://bigquery.googleapis.com/mcp`) alongside **Google's official `MCP Toolbox for Databases`** for AWS PostgreSQL & AWS MySQL.

> **Side-by-Side Isolation**: Everything in `src_v3_native_bq/` uses `_v3` / `-v3` identifiers so your existing `v1` ([`../src/`](../src)) and `v2` ([`../src_mcptoolbox/`](../src_mcptoolbox)) deployments remain 100% untouched.

---

## 1. `v3` Architecture Overview (Zero Custom MCP Server Code)

```text
  [ Business User — Gemini Enterprise / Vertex AI Playground ]
                                │
                                ▼
  ╔══════════════════════════════════════════════════════════════════════════╗
  ║  Vertex AI Agent Engine: Sentinel — Customer 360 & Risk Advisor_v3       ║
  ║  • Dual Auth Toolsets:                                                   ║
  ║    1. CloudRunOIDCMcpToolset  -> OIDC ID Token (Cloud Run IAM)           ║
  ║    2. GoogleApiOAuthMcpToolset -> OAuth2 Token + x-goog-user-project     ║
  ║       + Read-Only ToolPredicate (blocks write-capable `execute_sql`)     ║
  ╚══════════════════════╤═══════════════════════════════════╤═══════════════╝
                         │ OIDC Bearer                       │ OAuth2 Bearer
                         ▼                                   ▼
  ┌─────────────────────────────────────────┐   ┌──────────────────────────────────────────┐
  │ Cloud Run: mcp-toolbox-databases-v2     │   │ Google Managed: bigquery.googleapis.com  │
  │ • Image: Official Google MCP Toolbox    │   │ • Endpoint: https://bigquery.googleapis  │
  │ • Scoped to AWS Operational Tools Only  │   │   .com/mcp (0 Cloud Run containers!)     │
  │ • Go-native connection pooling          │   │ • Exposed: execute_sql_readonly +        │
  │ • 7 parameterized PG & MySQL tools      │   │   dataset/table metadata discovery       │
  └──────┬──────────────────┬───────────────┘   └────────────────────┬─────────────────────┘
         │ Pooled TCP 5432  │ Pooled TCP 3306                        │ Native BQ Slots
         ▼                  ▼                                        ▼
  ┌──────────────┐   ┌──────────────┐                       ┌──────────────────────────────┐
  │ AWS Postgres │   │  AWS MySQL   │                       │  GCP BigQuery (`ccca`)       │
  │ `finance_db` │   │`engagement_db│                       │  • Dataset-scoped IAM READER │
  └──────────────┘   └──────────────┘                       └──────────────────────────────┘
```

---

## 2. Evolution Across `v1` → `v2` → `v3`

| Dimension | `v1` ([`../src/`](../src)) | `v2` ([`../src_mcptoolbox/`](../src_mcptoolbox)) | `v3` (`src_v3_native_bq/`) |
| :--- | :--- | :--- | :--- |
| **Custom MCP Python Code** | 3 custom servers (~550 LOC, 3 Dockerfiles) | 1 custom BQ server (`main_v2.py`, 246 LOC, 1 Dockerfile) | **0 lines of custom MCP server code, 0 Dockerfiles** |
| **Cloud Run Services to Host** | 3 (`db-query-api`, `db-query-api-mysql`, `mcp-server-bigquery`) | 2 (`mcp-toolbox-databases-v2`, `mcp-server-bigquery-v2`) | **1** (`mcp-toolbox-databases-v2` for AWS OLTP only) |
| **BigQuery MCP Endpoint** | Custom Cloud Run `/mcp` | Custom Cloud Run `/mcp` | **Google Managed `https://bigquery.googleapis.com/mcp`** |
| **BigQuery Schema Discovery** | Hardcoded in Python string | Hardcoded in Python string | **Dynamic** (`list_dataset_ids`, `list_table_ids`, `get_table_info`) + fast-path prompt schema |
| **BigQuery Read-Only Safety** | Python prefix check | Custom regex validator | **3-Layer Defense**: `is_readonly_bq_mcp_tool` strips `execute_sql` + `execute_sql_readonly` server enforcement + dataset-scoped IAM `READER` |
| **Auth Protocol Split** | Static / OIDC | OIDC ID Tokens on both | **Dual Auth**: OIDC ID Token (Cloud Run) + OAuth2 Access Token & `x-goog-user-project` (`googleapis.com`) |

---

## 3. Quick Start (`agentic-mvp`)

### Step 1: Configure Native BigQuery MCP & Least-Privilege `v3` IAM
```bash
export PROJECT_ID="agentic-mvp"
export REGION="us-central1"
./src_v3_native_bq/scripts_v3/setup_v3.sh
```

### Step 2: Run Guardrail Verification Tests
```bash
./.venv/bin/python ./src_v3_native_bq/tests_v3/verify_v3.py
# Add --live once local ADC is active:
./.venv/bin/python ./src_v3_native_bq/tests_v3/verify_v3.py --live
```

### Step 3: Deploy `Sentinel — Customer 360 & Risk Advisor_v3` to Vertex AI Agent Engine
```bash
adk deploy agent_engine \
  --project="agentic-mvp" \
  --region="us-central1" \
  --display_name="Sentinel — Customer 360 & Risk Advisor_v3" \
  --service_account="ccca-agent-caller-v3@agentic-mvp.iam.gserviceaccount.com" \
  --otel_to_cloud \
  ./src_v3_native_bq/sentinel_customer_360_advisor_v3
```
