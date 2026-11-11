# Cross-Cloud Conversational Analytics

Zero-copy **Cross-Cloud Conversational Analytics** across **AWS** operational databases (`PostgreSQL`, `MySQL`) and **Google Cloud BigQuery** (`66.0M+` rows) powered by **Vertex AI Agent Engine (`google-adk`)**, **Gemini Enterprise**, and **Model Context Protocol (MCP)** on **Google Cloud Run**.

## Repository Structure

* **[`src/`](./src)** — **MCP Servers & Deployment Code**:
  * [`src/mcp-server-postgres/`](./src/mcp-server-postgres) — Cloud Run MCP bridge for AWS PostgreSQL (`finance_db`).
  * [`src/mcp-server-mysql/`](./src/mcp-server-mysql) — Cloud Run MCP bridge for AWS MySQL (`engagement_db`).
  * [`src/mcp-server-bigquery/`](./src/mcp-server-bigquery) — Cloud Run MCP server for GCP BigQuery (`ccca`).
  * [`src/AGENT_PROMPT.md`](./src/AGENT_PROMPT.md) — Analytics Agent system prompt & cross-cloud join strategy.
  * [`src/scripts/`](./src/scripts) & [`src/infra-aws/`](./src/infra-aws) — Cloud Run deployment script, synthetic cross-DB seeder, and optional AWS demo Terraform.
  * [`src/how-to-setup.md`](./src/how-to-setup.md) — End-to-end deployment & verification guide.
* **[`doc/`](./doc)** — **Interactive Google Cloud Executive Brief & 5-Slide Pitch Portal**:
  * Interactive `< Prev` / `Next >` multi-hop flow visualizer (`User ↔ Analytics Agent ↔ Cloud Run MCP ↔ AWS PostgreSQL, AWS MySQL & GCP BigQuery`) and 5-slide executive presentation.

## Run the Interactive Web Portal Locally

```bash
python3 -m http.server 8999 --bind 127.0.0.1 --directory ./doc
```

Open `http://127.0.0.1:8999/` in your browser.

## Deploy the Cloud Run MCP Servers

```bash
export PROJECT_ID="<YOUR_GCP_PROJECT_ID>"
export REGION="us-west1"

./src/scripts/deploy.sh postgres
./src/scripts/deploy.sh mysql
./src/scripts/deploy.sh bigquery
```
