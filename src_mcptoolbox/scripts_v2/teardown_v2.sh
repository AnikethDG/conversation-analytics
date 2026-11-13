#!/usr/bin/env bash
#
# Teardown script for ALL P0 `_v2` PoC resources in Google Cloud.
# Leaves all original v1 resources (db-query-api, db-query-api-mysql,
# mcp-server-bigquery, and existing v1 Analytics Agent) 100% untouched.
#
# Usage:
#   PROJECT_ID="<YOUR_GCP_PROJECT_ID>" ./src_mcptoolbox/scripts_v2/teardown_v2.sh

set -euo pipefail

PROJECT_ID="${PROJECT_ID:?Please set PROJECT_ID to your Google Cloud project ID}"
REGION="${REGION:-us-west1}"
REPOSITORY="${REPOSITORY:-cloud-run-source-deploy}"
MCP_SA_EMAIL="ccca-mcp-runner-v2@${PROJECT_ID}.iam.gserviceaccount.com"
AGENT_SA_EMAIL="ccca-agent-caller-v2@${PROJECT_ID}.iam.gserviceaccount.com"

export CLOUDSDK_METRICS_ENVIRONMENT="${CLOUDSDK_METRICS_ENVIRONMENT:+$CLOUDSDK_METRICS_ENVIRONMENT }datacloud.antigravity"

if [ -z "${CLOUDSDK_AUTH_ACCESS_TOKEN:-}" ]; then
  CLOUDSDK_AUTH_ACCESS_TOKEN="$(python3 -c 'import google.auth, google.auth.transport.requests as r; c,_=google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"]); c.refresh(r.Request()); print(c.token)')"
  export CLOUDSDK_AUTH_ACCESS_TOKEN
fi

echo "================================================================="
echo "Tearing down P0 _v2 PoC resources in ${PROJECT_ID} (${REGION})"
echo "Original v1 services & v1 Analytics Agent will NOT be touched."
echo "================================================================="

# 0. Delete _v2 Gemini Enterprise Agent registrations & _v2 Vertex AI Agent Engine instances
PROJECT_ID="${PROJECT_ID}" REGION="${REGION}" TOKEN="${CLOUDSDK_AUTH_ACCESS_TOKEN}" python3 - <<'PYEOF'
import json, os, urllib.request, urllib.error

project = os.environ["PROJECT_ID"]
region = os.environ["REGION"]
token = os.environ["TOKEN"]
headers = {"Authorization": f"Bearer {token}", "x-goog-user-project": project}

# 0a. Delete any Gemini Enterprise agent ending in '_v2' across all engines
engines_url = f"https://discoveryengine.googleapis.com/v1alpha/projects/{project}/locations/global/collections/default_collection/engines"
try:
    with urllib.request.urlopen(urllib.request.Request(engines_url, headers=headers), timeout=20) as r:
        ge_engines = json.loads(r.read().decode()).get("engines", [])
    for ge in ge_engines:
        eng_name = ge.get("name", "")
        agents_url = f"https://discoveryengine.googleapis.com/v1alpha/{eng_name}/assistants/default_assistant/agents"
        with urllib.request.urlopen(urllib.request.Request(agents_url, headers=headers), timeout=20) as ar:
            ge_agents = json.loads(ar.read().decode()).get("agents", [])
        for ag in ge_agents:
            if ag.get("displayName", "").endswith("_v2"):
                ag_name = ag["name"]
                print(f"Deleting Gemini Enterprise Agent: {ag.get('displayName')} ({ag_name})...")
                del_req = urllib.request.Request(f"https://discoveryengine.googleapis.com/v1alpha/{ag_name}", method="DELETE", headers=headers)
                with urllib.request.urlopen(del_req, timeout=20) as dr:
                    dr.read()
except Exception as exc:
    print(f"  Note checking Gemini Enterprise agents: {exc}")

# 0b. Delete any Vertex AI ReasoningEngine ending in '_v2'
list_url = f"https://{region}-aiplatform.googleapis.com/v1beta1/projects/{project}/locations/{region}/reasoningEngines"
try:
    with urllib.request.urlopen(urllib.request.Request(list_url, headers=headers), timeout=20) as r:
        engines = json.loads(r.read().decode()).get("reasoningEngines", [])
    for eng in engines:
        disp = eng.get("displayName", "")
        name = eng.get("name", "")
        if disp.endswith("_v2"):
            print(f"Deleting Vertex AI Agent Engine: {disp} ({name})...")
            del_url = f"https://{region}-aiplatform.googleapis.com/v1beta1/{name}?force=true"
            req = urllib.request.Request(del_url, method="DELETE", headers=headers)
            with urllib.request.urlopen(req, timeout=30) as dr:
                dr.read()
except Exception as exc:
    print(f"  Note checking ReasoningEngines: {exc}")
PYEOF

# 1. Delete _v2 Cloud Run services
for SVC in "mcp-toolbox-databases-v2" "mcp-server-bigquery-v2"; do
  echo "Deleting Cloud Run service ${SVC} (if present)..."
  gcloud run services delete "${SVC}" \
    --region="${REGION}" \
    --project="${PROJECT_ID}" \
    --quiet 2>/dev/null || echo "  (Already absent: ${SVC})"
done

# 2. Delete _v2 Secret Manager secrets
for SEC in "ccca_pg_password_v2" "ccca_mysql_password_v2" "ccca_toolbox_config_v2"; do
  echo "Deleting Secret Manager secret ${SEC} (if present)..."
  gcloud secrets delete "${SEC}" \
    --project="${PROJECT_ID}" \
    --quiet 2>/dev/null || echo "  (Already absent: ${SEC})"
done

# 3. Delete _v2 Artifact Registry image package
IMAGE_PKG="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/mcp-server-bigquery-v2"
echo "Deleting Artifact Registry image ${IMAGE_PKG} (if present)..."
gcloud artifacts docker images delete "${IMAGE_PKG}" \
  --delete-tags \
  --quiet 2>/dev/null || echo "  (Already absent: ${IMAGE_PKG})"

# 4. Delete _v2 Service Accounts
for SA in "${MCP_SA_EMAIL}" "${AGENT_SA_EMAIL}"; do
  echo "Deleting Service Account ${SA} (if present)..."
  gcloud iam service-accounts delete "${SA}" \
    --project="${PROJECT_ID}" \
    --quiet 2>/dev/null || echo "  (Already absent: ${SA})"
done

echo "================================================================="
echo "Teardown of all _v2 PoC resources complete!"
echo "================================================================="
