"""Versioned ADK Analytics Agent v2 (P0-4).

Connects Vertex AI Gemini (via google-adk) to IAM-authenticated Cloud Run
MCP v2 endpoints:
  1. Official Google MCP Toolbox (`mcp-toolbox-databases-v2`)
  2. Guardrailed BigQuery MCP (`mcp-server-bigquery-v2`)
"""

import asyncio
import os
from pathlib import Path
import subprocess
import time
from typing import Any, Dict, List

import google.auth
from google.auth.transport.requests import Request
from google.oauth2 import id_token

PROMPT_PATH = Path(__file__).with_name("prompt_v2.md")


def get_cloud_run_id_token(target_audience: str) -> str:
    """Obtains a Google-signed OIDC ID token for IAM-authenticated Cloud Run."""
    req = Request()
    creds, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    creds.refresh(req)
    if getattr(creds, "id_token", None):
        return creds.id_token
    try:
        return id_token.fetch_id_token(req, target_audience)
    except Exception:
        env = os.environ.copy()
        env["CLOUDSDK_AUTH_ACCESS_TOKEN"] = creds.token
        env["CLOUDSDK_METRICS_ENVIRONMENT"] = (
            env.get("CLOUDSDK_METRICS_ENVIRONMENT", "") + " datacloud.antigravity"
        ).strip()
        return subprocess.check_output(
            ["gcloud", "auth", "print-identity-token"], env=env, text=True
        ).strip()


def build_analytics_agent_v2(
    toolbox_mcp_url: str,
    bigquery_mcp_url: str,
    model_name: str = "gemini-3-flash-preview",
):
    """Constructs the google-adk LlmAgent wired to both IAM-locked _v2 MCP servers."""
    import urllib.parse
    from google.adk.agents import LlmAgent
    from google.adk.models import Gemini
    from google.adk.tools.mcp_tool import MCPToolset, StreamableHTTPConnectionParams

    tb_p = urllib.parse.urlparse(toolbox_mcp_url)
    bq_p = urllib.parse.urlparse(bigquery_mcp_url)
    toolbox_base = f"{tb_p.scheme}://{tb_p.netloc}"
    bq_base = f"{bq_p.scheme}://{bq_p.netloc}"

    tb_token = get_cloud_run_id_token(toolbox_base)
    bq_token = get_cloud_run_id_token(bq_base)

    toolbox_toolset = MCPToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=toolbox_mcp_url,
            headers={"Authorization": f"Bearer {tb_token}"},
            timeout=30.0,
        )
    )
    bigquery_v2_toolset = MCPToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=bigquery_mcp_url,
            headers={"Authorization": f"Bearer {bq_token}"},
            timeout=30.0,
        )
    )

    model_loc = os.environ.get("AGENT_MODEL_LOCATION_V2", "global")
    return LlmAgent(
        name="analytics_agent_v2",
        model=Gemini(model=model_name, client_kwargs={"location": model_loc}),
        instruction=PROMPT_PATH.read_text(encoding="utf-8"),
        tools=[toolbox_toolset, bigquery_v2_toolset],
    )


async def run_agent_turn_v2(
    prompt: str,
    toolbox_mcp_url: str,
    bigquery_mcp_url: str,
    project_id: str | None = None,
    location: str = "global",
    model_name: str = "gemini-3-flash-preview",
) -> Dict[str, Any]:
    """Executes a single conversational turn on analytics_agent_v2 and captures telemetry."""
    from google.adk.runners import InMemoryRunner
    from google.genai import types as genai_types

    resolved_project = (
        project_id
        or os.environ.get("PROJECT_ID")
        or os.environ.get("GOOGLE_CLOUD_PROJECT")
    )
    if not resolved_project:
        raise ValueError("Set PROJECT_ID or GOOGLE_CLOUD_PROJECT environment variable.")

    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "1"
    os.environ["GOOGLE_CLOUD_PROJECT"] = resolved_project
    os.environ["GOOGLE_CLOUD_LOCATION"] = location

    agent = build_analytics_agent_v2(
        toolbox_mcp_url=toolbox_mcp_url,
        bigquery_mcp_url=bigquery_mcp_url,
        model_name=model_name,
    )
    runner = InMemoryRunner(agent=agent, app_name="ccca_eval_v2")
    session = await runner.session_service.create_session(
        app_name="ccca_eval_v2", user_id="eval_user_v2"
    )

    t0 = time.perf_counter()
    tool_calls: List[str] = []
    final_text_parts: List[str] = []
    prompt_tokens = 0
    candidate_tokens = 0

    msg = genai_types.Content(
        role="user", parts=[genai_types.Part.from_text(text=prompt)]
    )

    try:
        async for event in runner.run_async(
            user_id="eval_user_v2", session_id=session.id, new_message=msg
        ):
            if getattr(event, "usage_metadata", None):
                prompt_tokens += int(
                    getattr(event.usage_metadata, "prompt_token_count", 0) or 0
                )
                candidate_tokens += int(
                    getattr(event.usage_metadata, "candidates_token_count", 0) or 0
                )
            content = getattr(event, "content", None)
            if content and getattr(content, "parts", None):
                for part in content.parts:
                    fc = getattr(part, "function_call", None)
                    if fc and getattr(fc, "name", None):
                        tool_calls.append(fc.name)
                    if event.is_final_response() and getattr(part, "text", None):
                        final_text_parts.append(part.text)
    finally:
        await runner.close()

    elapsed_s = round(time.perf_counter() - t0, 2)
    return {
        "prompt": prompt,
        "latency_s": elapsed_s,
        "tool_calls": tool_calls,
        "prompt_tokens": prompt_tokens,
        "candidate_tokens": candidate_tokens,
        "total_tokens": prompt_tokens + candidate_tokens,
        "answer": "\n".join(final_text_parts).strip(),
    }


if __name__ == "__main__":
    tb_url = os.environ["TOOLBOX_MCP_V2_URL"]
    bq_url = os.environ["BQ_MCP_V2_URL"]
    sample_q = (
        "Look up James Smith in Postgres, check his support tickets in MySQL, "
        "and get his fraud and churn risk scores in BigQuery."
    )
    res = asyncio.run(run_agent_turn_v2(sample_q, tb_url, bq_url))
    print("Tools invoked:", res["tool_calls"])
    print(f"Latency: {res['latency_s']}s | Tokens: {res['total_tokens']}")
    print("Answer:\n", res["answer"])
