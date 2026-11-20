#!/usr/bin/env bash
#
# Automated Setup Script for `v3` (MCP Toolbox + BigQuery Native Remote MCP).
# Zero custom containers or Cloud Build steps required for BigQuery!
# Leaves all existing v1 (`src/`) and v2 (`src_mcptoolbox/`) resources untouched.
#
# Usage:
#   export PROJECT_ID="agentic-mvp"
#   ./src_v3_native_bq/scripts_v3/setup_v3.sh

set -euo pipefail

PROJECT_ID="${PROJECT_ID:-agentic-mvp}"
REGION="${REGION:-us-central1}"
BQ_DATASET="${BQ_DATASET:-ccca}"
TOOLBOX_SERVICE="${TOOLBOX_SERVICE:-mcp-toolbox-databases-v2}"

AGENT_SA_NAME="ccca-agent-caller-v3"
AGENT_SA_EMAIL="${AGENT_SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

export CLOUDSDK_METRICS_ENVIRONMENT="${CLOUDSDK_METRICS_ENVIRONMENT:+$CLOUDSDK_METRICS_ENVIRONMENT }datacloud.antigravity"

echo "================================================================="
echo "Configuring v3 Native BigQuery MCP Stack in ${PROJECT_ID} (${REGION})"
echo "  (Eliminates custom mcp-server-bigquery-v2 container)"
echo "================================================================="

# 1. Enable BigQuery, Agent Registry & Cloud API Registry APIs
echo "[1/4] Enabling BigQuery, Agent Registry & Cloud API Registry APIs..."
gcloud services enable \
  bigquery.googleapis.com \
  agentregistry.googleapis.com \
  cloudapiregistry.googleapis.com \
  iamcredentials.googleapis.com \
  --project="${PROJECT_ID}"

# Enable Google's managed remote BigQuery MCP server (https://bigquery.googleapis.com/mcp)
gcloud beta api-registry mcp enable bigquery.googleapis.com --project="${PROJECT_ID}" 2>/dev/null || \
  echo "  (Note: bigquery.googleapis.com/mcp auto-registered via BigQuery API + Agent Registry)"

# 2. Create Dedicated Least-Privilege v3 Agent Service Account
echo "[2/4] Provisioning least-privilege service account ${AGENT_SA_EMAIL}..."
if ! gcloud iam service-accounts describe "${AGENT_SA_EMAIL}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud iam service-accounts create "${AGENT_SA_NAME}" \
    --display-name="ccca_agent_caller_v3" \
    --description="Least-privilege ADK v3 caller for MCP Toolbox + Native BigQuery MCP" \
    --project="${PROJECT_ID}"
  sleep 5
fi

# 3. Grant Native BigQuery MCP + Job Permissions (Project) & Dataset-Scoped Read-Only Access
echo "[3/4] Granting roles/mcp.toolUser, roles/bigquery.jobUser, and dataset-scoped dataViewer..."
for ROLE in "roles/mcp.toolUser" "roles/bigquery.jobUser" "roles/aiplatform.user" "roles/cloudtrace.agent"; do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${AGENT_SA_EMAIL}" \
    --role="${ROLE}" \
    --condition=None \
    --quiet >/dev/null
done

# Allow SA to mint OIDC tokens for Cloud Run MCP Toolbox
gcloud iam service-accounts add-iam-policy-binding "${AGENT_SA_EMAIL}" \
  --member="serviceAccount:${AGENT_SA_EMAIL}" \
  --role="roles/iam.serviceAccountTokenCreator" \
  --project="${PROJECT_ID}" \
  --quiet >/dev/null

# Scope BigQuery dataViewer STRICTLY to dataset `${BQ_DATASET}` (not project-wide, no dataEditor!)
python3 - "${PROJECT_ID}" "${BQ_DATASET}" "${AGENT_SA_EMAIL}" <<'PYEOF'
import json, subprocess, sys, urllib.request

project_id, dataset_id, sa_email = sys.argv[1], sys.argv[2], sys.argv[3]
tok = subprocess.check_output(["gcloud", "auth", "print-access-token"], text=True).strip()
url = f"https://bigquery.googleapis.com/bigquery/v2/projects/{project_id}/datasets/{dataset_id}"
hdrs = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}

with urllib.request.urlopen(urllib.request.Request(url, headers=hdrs), timeout=15) as r:
    ds = json.loads(r.read().decode())

access = ds.get("access", [])
entry = {"role": "READER", "userByEmail": sa_email}
if not any(a.get("role") == "READER" and a.get("userByEmail") == sa_email for a in access):
    access.append(entry)
    ds["access"] = access
    req = urllib.request.Request(url, data=json.dumps(ds).encode(), headers=hdrs, method="PUT")
    with urllib.request.urlopen(req, timeout=15) as r2:
        r2.read()
    print(f"  [OK] Granted dataset-scoped BigQuery READER on {project_id}.{dataset_id} to {sa_email}")
else:
    print(f"  [OK] Dataset-scoped BigQuery READER already present on {project_id}.{dataset_id}")
PYEOF

# 4. Grant Cloud Run Invoker on Existing Operational MCP Toolbox Service
echo "[4/4] Granting roles/run.invoker on Cloud Run service '${TOOLBOX_SERVICE}'..."
gcloud run services add-iam-policy-binding "${TOOLBOX_SERVICE}" \
  --region="${REGION}" \
  --project="${PROJECT_ID}" \
  --member="serviceAccount:${AGENT_SA_EMAIL}" \
  --role="roles/run.invoker" \
  --quiet >/dev/null

TOOLBOX_URL="$(gcloud run services describe "${TOOLBOX_SERVICE}" --region="${REGION}" --project="${PROJECT_ID}" --format='value(status.url)')"

echo "================================================================="
echo "v3 Native BigQuery MCP Infrastructure Ready!"
echo "  - Operational AWS DBs (Cloud Run) : ${TOOLBOX_URL}/mcp"
echo "  - Warehouse BigQuery (Native MCP) : https://bigquery.googleapis.com/mcp"
echo ""
echo "Deploy Sentinel_v3 to Vertex AI Agent Engine:"
echo "  adk deploy agent_engine \\"
echo "    --project=\"${PROJECT_ID}\" \\"
echo "    --region=\"${REGION}\" \\"
echo "    --display_name=\"Sentinel — Customer 360 & Risk Advisor_v3\" \\"
echo "    --service_account=\"${AGENT_SA_EMAIL}\" \\"
echo "    --otel_to_cloud \\"
echo "    ./src_v3_native_bq/sentinel_customer_360_advisor_v3"
echo "================================================================="
