#!/usr/bin/env bash
#
# Automated Deployment Script for P0 `_v2` Cross-Cloud Conversational Analytics PoC.
# Leaves all existing v1 resources 100% untouched and tags/names every new
# resource with `_v2` / `-v2` + label `poc_version=v2` for 1-command teardown.
#
# Usage:
#   export PROJECT_ID="<YOUR_GCP_PROJECT_ID>"
#   export POSTGRES_HOST="..." POSTGRES_USER="postgres" POSTGRES_PASSWORD="..."
#   export MYSQL_HOST="..."    MYSQL_USER="admin"       MYSQL_PASSWORD="..."
#   ./src_mcptoolbox/scripts_v2/deploy_v2.sh

set -euo pipefail

PROJECT_ID="${PROJECT_ID:?Please set PROJECT_ID to your Google Cloud project ID}"
REGION="${REGION:-us-west1}"
REPOSITORY="${REPOSITORY:-cloud-run-source-deploy}"
TOOLBOX_IMAGE="${TOOLBOX_IMAGE:-us-central1-docker.pkg.dev/database-toolbox/toolbox/toolbox:latest}"

POSTGRES_HOST="${POSTGRES_HOST:?Please set POSTGRES_HOST}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
POSTGRES_DB="${POSTGRES_DB:-finance_db}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:?Please set POSTGRES_PASSWORD}"

MYSQL_HOST="${MYSQL_HOST:?Please set MYSQL_HOST}"
MYSQL_PORT="${MYSQL_PORT:-3306}"
MYSQL_DB="${MYSQL_DB:-engagement_db}"
MYSQL_USER="${MYSQL_USER:-admin}"
MYSQL_PASSWORD="${MYSQL_PASSWORD:?Please set MYSQL_PASSWORD}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
V2_ROOT="$(dirname "${SCRIPT_DIR}")"
TOOLS_YAML_PATH="${V2_ROOT}/mcp_toolbox_v2/tools_v2.yaml"
BQ_MCP_DIR="${V2_ROOT}/mcp_bigquery_v2"

SA_NAME="ccca-mcp-runner-v2"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

export CLOUDSDK_METRICS_ENVIRONMENT="${CLOUDSDK_METRICS_ENVIRONMENT:+$CLOUDSDK_METRICS_ENVIRONMENT }datacloud.antigravity"

if [ -z "${CLOUDSDK_AUTH_ACCESS_TOKEN:-}" ]; then
  CLOUDSDK_AUTH_ACCESS_TOKEN="$(python3 -c 'import google.auth, google.auth.transport.requests as r; c,_=google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"]); c.refresh(r.Request()); print(c.token)')"
  export CLOUDSDK_AUTH_ACCESS_TOKEN
fi

echo "================================================================="
echo "Deploying P0 _v2 Stack in ${PROJECT_ID} (${REGION})"
echo "  (v1 services db-query-api*, mcp-server-bigquery remain untouched)"
echo "================================================================="

# 0. Ensure Secret Manager API is enabled
gcloud services enable secretmanager.googleapis.com run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com bigquery.googleapis.com \
  --project="${PROJECT_ID}"

# 1. Create Dedicated Least-Privilege Service Account (ccca-mcp-runner-v2)
if ! gcloud iam service-accounts describe "${SA_EMAIL}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  echo "Creating dedicated service account ${SA_EMAIL}..."
  gcloud iam service-accounts create "${SA_NAME}" \
    --display-name="ccca_mcp_runner_v2" \
    --description="Least-privilege runtime SA for P0 _v2 MCP servers" \
    --project="${PROJECT_ID}"
  sleep 5
fi

echo "Granting BigQuery JobUser & DataViewer permissions to ${SA_EMAIL}..."
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/bigquery.jobUser" \
  --condition=None \
  --quiet >/dev/null

gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/bigquery.dataViewer" \
  --condition=None \
  --quiet >/dev/null

gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/monitoring.metricWriter" \
  --condition=None \
  --quiet >/dev/null

# 2. Upsert _v2 Secrets in Google Cloud Secret Manager (P0-3)
upsert_secret() {
  local secret_name="$1"
  local secret_file="$2"
  if ! gcloud secrets describe "${secret_name}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
    gcloud secrets create "${secret_name}" \
      --replication-policy="automatic" \
      --labels="poc_version=v2,app=ccca_v2" \
      --project="${PROJECT_ID}" >/dev/null
  fi
  gcloud secrets versions add "${secret_name}" \
    --data-file="${secret_file}" \
    --project="${PROJECT_ID}" >/dev/null

  gcloud secrets add-iam-policy-binding "${secret_name}" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/secretmanager.secretAccessor" \
    --project="${PROJECT_ID}" \
    --quiet >/dev/null
}

echo "Upserting _v2 secrets in Secret Manager..."
TMP_PG="$(mktemp)"
TMP_MY="$(mktemp)"
trap 'rm -f "${TMP_PG}" "${TMP_MY}"' EXIT
printf '%s' "${POSTGRES_PASSWORD}" > "${TMP_PG}"
printf '%s' "${MYSQL_PASSWORD}" > "${TMP_MY}"

upsert_secret "ccca_pg_password_v2" "${TMP_PG}"
upsert_secret "ccca_mysql_password_v2" "${TMP_MY}"
upsert_secret "ccca_toolbox_config_v2" "${TOOLS_YAML_PATH}"

# 3. Deploy Official Google MCP Toolbox for Databases (mcp-toolbox-databases-v2) [P0-1 + P0-3]
echo "Deploying Cloud Run service: mcp-toolbox-databases-v2 (IAM-authenticated)..."
gcloud run deploy "mcp-toolbox-databases-v2" \
  --image="${TOOLBOX_IMAGE}" \
  --region="${REGION}" \
  --platform="managed" \
  --service-account="${SA_EMAIL}" \
  --no-allow-unauthenticated \
  --port=8080 \
  --cpu=1 \
  --memory="512Mi" \
  --min-instances=0 \
  --max-instances=5 \
  --labels="poc_version=v2,app=ccca_v2" \
  --args="--config=/secrets/tools_v2.yaml,--address=0.0.0.0,--port=8080,--telemetry-gcp" \
  --set-env-vars="POSTGRES_HOST=${POSTGRES_HOST},POSTGRES_PORT=${POSTGRES_PORT},POSTGRES_DB=${POSTGRES_DB},POSTGRES_USER=${POSTGRES_USER},MYSQL_HOST=${MYSQL_HOST},MYSQL_PORT=${MYSQL_PORT},MYSQL_DB=${MYSQL_DB},MYSQL_USER=${MYSQL_USER},BQ_PROJECT_ID=${PROJECT_ID}" \
  --set-secrets="/secrets/tools_v2.yaml=ccca_toolbox_config_v2:latest,POSTGRES_PASSWORD=ccca_pg_password_v2:latest,MYSQL_PASSWORD=ccca_mysql_password_v2:latest" \
  --project="${PROJECT_ID}"

# 4. Build & Deploy Guardrailed BigQuery MCP Server (mcp-server-bigquery-v2) [P0-2 + P0-3]
BQ_IMAGE_URI="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/mcp-server-bigquery-v2:latest"
echo "Building mcp-server-bigquery-v2 container via Cloud Build..."
gcloud builds submit "${BQ_MCP_DIR}" \
  --tag="${BQ_IMAGE_URI}" \
  --project="${PROJECT_ID}"

echo "Deploying Cloud Run service: mcp-server-bigquery-v2 (IAM-authenticated)..."
gcloud run deploy "mcp-server-bigquery-v2" \
  --image="${BQ_IMAGE_URI}" \
  --region="${REGION}" \
  --platform="managed" \
  --service-account="${SA_EMAIL}" \
  --no-allow-unauthenticated \
  --port=8080 \
  --cpu=1 \
  --memory="512Mi" \
  --min-instances=0 \
  --max-instances=5 \
  --labels="poc_version=v2,app=ccca_v2" \
  --set-env-vars="BQ_PROJECT_ID=${PROJECT_ID},BQ_DATASET=ccca,BQ_MAX_SCAN_BYTES=5368709120,BQ_MAX_CONTEXT_ROWS=50" \
  --project="${PROJECT_ID}"

TOOLBOX_URL="$(gcloud run services describe mcp-toolbox-databases-v2 --region="${REGION}" --project="${PROJECT_ID}" --format='value(status.url)')"
BQ_V2_URL="$(gcloud run services describe mcp-server-bigquery-v2 --region="${REGION}" --project="${PROJECT_ID}" --format='value(status.url)')"

echo "================================================================="
echo "P0 _v2 Cloud Run Services Deployed Successfully!"
echo "  1. Official MCP Toolbox v2 : ${TOOLBOX_URL}/mcp"
echo "  2. Guardrailed BigQuery v2 : ${BQ_V2_URL}/mcp"
echo "================================================================="
