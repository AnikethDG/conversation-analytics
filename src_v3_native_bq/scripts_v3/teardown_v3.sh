#!/usr/bin/env bash
#
# 1-Command Teardown for `v3` resources (`_v3` Agent Engine + `ccca-agent-caller-v3`).
# Leaves all v1 (`src/`) and v2 (`src_mcptoolbox/`) services untouched.

set -euo pipefail

PROJECT_ID="${PROJECT_ID:-agentic-mvp}"
REGION="${REGION:-us-central1}"
AGENT_SA_EMAIL="ccca-agent-caller-v3@${PROJECT_ID}.iam.gserviceaccount.com"

export CLOUDSDK_METRICS_ENVIRONMENT="${CLOUDSDK_METRICS_ENVIRONMENT:+$CLOUDSDK_METRICS_ENVIRONMENT }datacloud.antigravity"

echo "================================================================="
echo "Tearing down v3 resources in ${PROJECT_ID} (${REGION})"
echo "  (v1 & v2 services remain untouched)"
echo "================================================================="

TOKEN="$(gcloud auth print-access-token)"
PROJECT_ID="${PROJECT_ID}" REGION="${REGION}" TOKEN="${TOKEN}" python3 - <<'PYEOF'
import json, os, urllib.request

project = os.environ["PROJECT_ID"]
region = os.environ["REGION"]
headers = {"Authorization": f"Bearer {os.environ['TOKEN']}", "x-goog-user-project": project}

list_url = f"https://{region}-aiplatform.googleapis.com/v1beta1/projects/{project}/locations/{region}/reasoningEngines"
try:
    with urllib.request.urlopen(urllib.request.Request(list_url, headers=headers), timeout=20) as r:
        engines = json.loads(r.read().decode()).get("reasoningEngines", [])
    for eng in engines:
        if eng.get("displayName", "").endswith("_v3"):
            del_url = f"https://{region}-aiplatform.googleapis.com/v1beta1/{eng['name']}?force=true"
            with urllib.request.urlopen(urllib.request.Request(del_url, method="DELETE", headers=headers), timeout=30) as dr:
                dr.read()
            print(f"Deleted Vertex AI Agent Engine: {eng.get('displayName')}")
except Exception as exc:
    print(f"  Note checking ReasoningEngines: {exc}")
PYEOF

gcloud iam service-accounts delete "${AGENT_SA_EMAIL}" \
  --project="${PROJECT_ID}" \
  --quiet 2>/dev/null || echo "  (Already absent: ${AGENT_SA_EMAIL})"

echo "Teardown of v3 resources complete!"
