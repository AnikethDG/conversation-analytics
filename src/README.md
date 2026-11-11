# Cross-Cloud Conversational Analytics — MCP Servers & Deployment Source (`src/`)

Source implementation for the **Cross-Cloud Conversational Analytics** solution bridging **AWS** operational databases (`PostgreSQL`, `MySQL`) and **Google Cloud BigQuery** (`ccca`) via serverless **Model Context Protocol (MCP)** bridges on **Google Cloud Run**.

## Directory Structure

```text
src/
├── README.md                    # Architecture & quickstart overview
├── how-to-setup.md              # Step-by-step Cloud Run & Secret Manager deployment guide
├── AGENT_PROMPT.md              # System prompt & cross-cloud join rules for Analytics Agent
├── DB_INFO.md                   # Polyglot schemas (AWS Postgres, AWS MySQL, GCP BigQuery)
├── MCP_ENGG.md                  # Engineering notes (stateless JSON-RPC, async pool, read-only guards)
├── mcp-server-postgres/         # Cloud Run MCP server for AWS PostgreSQL (finance_db)
│   ├── Dockerfile
│   ├── .gcloudignore
│   ├── main.py
│   └── requirements.txt
├── mcp-server-mysql/            # Cloud Run MCP server for AWS MySQL (engagement_db)
│   ├── Dockerfile
│   ├── .gcloudignore
│   ├── main.py
│   └── requirements.txt
├── mcp-server-bigquery/         # Cloud Run MCP server for GCP BigQuery (ccca)
│   ├── Dockerfile
│   ├── .gcloudignore
│   ├── main.py
│   └── requirements.txt
├── scripts/
│   ├── deploy.sh                # Cloud Build + IAM-authenticated Cloud Run deploy helper
│   └── seed_dbs.py              # Environment-driven synthetic data seeder (Postgres + MySQL)
└── infra-aws/
    └── main.tf                  # Optional Terraform setup for demo AWS PostgreSQL & MySQL
```

## Exposed MCP Tools

* **`query_postgres`** (`mcp-server-postgres`): Read-only SQL `SELECT` queries against `finance_db` (`customers`, `accounts`, `transactions`) with `default_transaction_read_only=on` and a 5-second `statement_timeout`.
* **`query_mysql`** (`mcp-server-mysql`): Read-only SQL `SELECT` queries against `engagement_db` (`support_tickets`, `campaign_responses`) with `SET SESSION TRANSACTION READ ONLY` and a 5-second read timeout.
* **`query_bigquery`** (`mcp-server-bigquery`): Read-only GoogleSQL `SELECT` queries against BigQuery dataset `ccca` (`app_events`, `customer_risk_profiles`) with a `10 GB` `maximum_bytes_billed` FinOps guardrail.

## Quick Deploy

```bash
export PROJECT_ID="<YOUR_GCP_PROJECT_ID>"
export REGION="us-west1"

./src/scripts/deploy.sh postgres
./src/scripts/deploy.sh mysql
./src/scripts/deploy.sh bigquery
```

See [`how-to-setup.md`](./how-to-setup.md) for full Secret Manager, IAM, and Agent registration steps.
