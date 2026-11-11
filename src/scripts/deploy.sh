#!/usr/bin/env bash
#
# Deployment script for Cross-Cloud Conversational Analytics MCP Servers.
# Builds the specified MCP server image via Google Cloud Build and deploys
# it to Google Cloud Run.
#
# Usage:
#   export PROJECT_ID="your-gcp-project-id"
#   export REGION="us-west1"
#   ./src/scripts/deploy.sh [postgres|mysql|bigquery]

set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Error: Specify a service to deploy (postgres, mysql, or bigquery)."
    echo "Usage: PROJECT_ID=<gcp-project> $0 [postgres|mysql|bigquery]"
    exit 1
fi

SERVICE_TYPE="$1"
PROJECT_ID="${PROJECT_ID:?Please set PROJECT_ID to your Google Cloud project ID}"
REGION="${REGION:-us-west1}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
REPOSITORY="${REPOSITORY:-cloud-run-source-deploy}"
ALLOW_UNAUTHENTICATED="${ALLOW_UNAUTHENTICATED:-false}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_ROOT="$(dirname "${SCRIPT_DIR}")"

case "${SERVICE_TYPE}" in
    postgres)
        SERVICE_NAME="db-query-api"
        FOLDER="${SRC_ROOT}/mcp-server-postgres"
        ;;
    mysql)
        SERVICE_NAME="db-query-api-mysql"
        FOLDER="${SRC_ROOT}/mcp-server-mysql"
        ;;
    bigquery)
        SERVICE_NAME="mcp-server-bigquery"
        FOLDER="${SRC_ROOT}/mcp-server-bigquery"
        ;;
    *)
        echo "Error: Unknown service '${SERVICE_TYPE}'. Allowed: postgres | mysql | bigquery"
        exit 1
        ;;
esac

IMAGE_URI="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${SERVICE_NAME}:${IMAGE_TAG}"

AUTH_FLAG="--no-allow-unauthenticated"
if [ "${ALLOW_UNAUTHENTICATED}" = "true" ]; then
    AUTH_FLAG="--allow-unauthenticated"
fi

echo "================================================================="
echo "Deploying ${SERVICE_NAME} to project ${PROJECT_ID} (${REGION})"
echo "================================================================="

echo "Step 1: Building and pushing image via Cloud Build..."
gcloud builds submit "${FOLDER}" \
    --tag "${IMAGE_URI}" \
    --project="${PROJECT_ID}"

echo "Step 2: Deploying Cloud Run service (${AUTH_FLAG})..."
gcloud run deploy "${SERVICE_NAME}" \
    --image "${IMAGE_URI}" \
    --region "${REGION}" \
    --platform="managed" \
    --port=8080 \
    "${AUTH_FLAG}" \
    --project="${PROJECT_ID}"

SERVICE_URL="$(gcloud run services describe "${SERVICE_NAME}" --region "${REGION}" --project "${PROJECT_ID}" --format 'value(status.url)')"
echo "================================================================="
echo "Deployment complete!"
echo "Service URL : ${SERVICE_URL}"
echo "MCP Endpoint: ${SERVICE_URL}/sse"
echo "================================================================="
