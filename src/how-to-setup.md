# How to Deploy & Configure the Cross-Cloud MCP Servers

End-to-end guide for deploying the three Cloud Run MCP database bridges (`PostgreSQL`, `MySQL`, and `BigQuery`) and connecting them to **Vertex AI Agent Engine** / **Gemini Enterprise**.

## Quick File Index

| Component | Path | Description |
| :--- | :--- | :--- |
| **PostgreSQL MCP Server** | [`mcp-server-postgres/main.py`](./mcp-server-postgres/main.py) | Read-only Cloud Run MCP server for AWS PostgreSQL (`finance_db`) |
| **MySQL MCP Server** | [`mcp-server-mysql/main.py`](./mcp-server-mysql/main.py) | Read-only Cloud Run MCP server for AWS MySQL (`engagement_db`) |
| **BigQuery MCP Server** | [`mcp-server-bigquery/main.py`](./mcp-server-bigquery/main.py) | Read-only Cloud Run MCP server for GCP BigQuery (`ccca`) |
| **Cloud Run Deploy Script** | [`scripts/deploy.sh`](./scripts/deploy.sh) | Automated Cloud Build + Cloud Run deployment |
| **Synthetic Data Seeder** | [`scripts/seed_dbs.py`](./scripts/seed_dbs.py) | Seeds 50 interconnected test records across PostgreSQL & MySQL |
| **AWS Demo DB Terraform** | [`infra-aws/main.tf`](./infra-aws/main.tf) | Optional Terraform setup for demo PostgreSQL + MySQL on AWS |
| **Agent System Prompt** | [`AGENT_PROMPT.md`](./AGENT_PROMPT.md) | Cross-cloud join & read-only prompt instructions |

---

## 1. Enable Google Cloud APIs & Artifact Registry

```bash
export PROJECT_ID="<YOUR_GCP_PROJECT_ID>"
export REGION="us-west1"

gcloud services enable \
    run.googleapis.com \
    cloudbuild.googleapis.com \
    artifactregistry.googleapis.com \
    secretmanager.googleapis.com \
    bigquery.googleapis.com \
    --project="${PROJECT_ID}"

gcloud artifacts repositories create cloud-run-source-deploy \
    --repository-format=docker \
    --location="${REGION}" \
    --description="Docker repository for Cross-Cloud MCP servers" \
    --project="${PROJECT_ID}"
```

## 2. Build & Deploy the Three MCP Servers

From the repository root:

```bash
./src/scripts/deploy.sh postgres
./src/scripts/deploy.sh mysql
./src/scripts/deploy.sh bigquery
```

By default, `deploy.sh` deploys with `--no-allow-unauthenticated` so only IAM-authorized callers (`roles/run.invoker`) can invoke the MCP endpoints.

## 3. Configure Database Connection Secrets on Cloud Run

Store operational database passwords in **Google Cloud Secret Manager** and bind them to Cloud Run:

```bash
# PostgreSQL MCP bridge
gcloud run services update db-query-api \
    --region="${REGION}" \
    --project="${PROJECT_ID}" \
    --set-env-vars="POSTGRES_HOST=<AWS_POSTGRES_HOST>,POSTGRES_PORT=5432,POSTGRES_DB=finance_db,POSTGRES_USER=postgres" \
    --set-secrets="POSTGRES_PASSWORD=postgres-db-password:latest"

# MySQL MCP bridge
gcloud run services update db-query-api-mysql \
    --region="${REGION}" \
    --project="${PROJECT_ID}" \
    --set-env-vars="MYSQL_HOST=<AWS_MYSQL_HOST>,MYSQL_PORT=3306,MYSQL_DB=engagement_db,MYSQL_USER=admin" \
    --set-secrets="MYSQL_PASSWORD=mysql-db-password:latest"

# BigQuery MCP server (uses Cloud Run service account ADC)
gcloud run services update mcp-server-bigquery \
    --region="${REGION}" \
    --project="${PROJECT_ID}" \
    --set-env-vars="BQ_DATASET=ccca"
```

## 4. Verify Tool Discovery & Read-Only Execution

```bash
TOKEN="$(gcloud auth print-identity-token)"
SERVICE_URL="$(gcloud run services describe db-query-api --region "${REGION}" --project "${PROJECT_ID}" --format 'value(status.url)')"

curl -s -X POST "${SERVICE_URL}/sse" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

## 5. Register MCP Endpoints with Analytics Agent

Register each Cloud Run URL (`https://<service-url>/sse` or `/mcp`) as an MCP toolset in **Vertex AI Agent Engine (`google-adk`)** or **Gemini Enterprise**, apply the system instructions in [`AGENT_PROMPT.md`](./AGENT_PROMPT.md), and grant the agent's identity `roles/run.invoker` on all three Cloud Run services.
