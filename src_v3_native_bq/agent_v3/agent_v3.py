"""Standalone Local ADK Runner for v3 (MCP Toolbox + Native BigQuery MCP).

Evaluates `sentinel_customer_360_advisor_v3` locally against:
  1. Cloud Run `MCP Toolbox` (OIDC ID token auth) for AWS Postgres & MySQL
  2. Native Managed BigQuery MCP (`https://bigquery.googleapis.com/mcp`, OAuth2
     access token + `x-goog-user-project` + read-only `tool_filter`)
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
import sys
import time
from typing import Any, Dict, List

V3_ROOT = Path(__file__).resolve().parents[1]
if str(V3_ROOT) not in sys.path:
    sys.path.insert(0, str(V3_ROOT))

from sentinel_customer_360_advisor_v3.agent import (  # noqa: E402
    CloudRunOIDCMcpToolset,
    GoogleApiOAuthMcpToolset,
    PROMPT_FILE,
    is_operational_aws_tool,
    is_readonly_bq_mcp_tool,
)


def build_analytics_agent_v3(
    toolbox_mcp_url: str,
    bq_project_id: str,
    bq_native_mcp_url: str = "https://bigquery.googleapis.com/mcp",
    model_name: str = "gemini-3-flash-preview",
    model_location: str = "global",
):
    """Constructs the v3 ADK LlmAgent wired to MCP Toolbox + Native BigQuery MCP."""
    from google.adk.agents import LlmAgent
    from google.adk.models import Gemini

    toolbox_toolset = CloudRunOIDCMcpToolset(
        url=toolbox_mcp_url,
        timeout=30.0,
        tool_filter=is_operational_aws_tool,
    )
    bq_native_toolset = GoogleApiOAuthMcpToolset(
        url=bq_native_mcp_url,
        billing_project_id=bq_project_id,
        timeout=30.0,
        tool_filter=is_readonly_bq_mcp_tool,
    )
    instruction = PROMPT_FILE.read_text(encoding="utf-8").replace(
        "{{BQ_PROJECT_ID}}", bq_project_id
    )
    return LlmAgent(
        name="analytics_agent_v3",
        model=Gemini(model=model_name, client_kwargs={"location": model_location}),
        instruction=instruction,
        tools=[toolbox_toolset, bq_native_toolset],
    )


async def run_agent_turn_v3(
    prompt: str,
    toolbox_mcp_url: str,
    bq_project_id: str | None = None,
    bq_native_mcp_url: str = "https://bigquery.googleapis.com/mcp",
    location: str = "global",
    model_name: str = "gemini-3-flash-preview",
) -> Dict[str, Any]:
    """Executes one conversational turn on analytics_agent_v3 and captures telemetry."""
    from google.adk.runners import InMemoryRunner
    from google.genai import types as genai_types

    resolved_project = (
        bq_project_id
        or os.environ.get("BQ_PROJECT_ID")
        or os.environ.get("PROJECT_ID")
        or os.environ.get("GOOGLE_CLOUD_PROJECT")
    )
    if not resolved_project:
        raise ValueError("Set BQ_PROJECT_ID, PROJECT_ID, or GOOGLE_CLOUD_PROJECT.")

    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "1"
    os.environ["GOOGLE_CLOUD_PROJECT"] = resolved_project
    os.environ["GOOGLE_CLOUD_LOCATION"] = location

    agent = build_analytics_agent_v3(
        toolbox_mcp_url=toolbox_mcp_url,
        bq_project_id=resolved_project,
        bq_native_mcp_url=bq_native_mcp_url,
        model_name=model_name,
        model_location=location,
    )
    runner = InMemoryRunner(agent=agent, app_name="ccca_eval_v3")
    session = await runner.session_service.create_session(
        app_name="ccca_eval_v3", user_id="eval_user_v3"
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
            user_id="eval_user_v3", session_id=session.id, new_message=msg
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

    return {
        "prompt": prompt,
        "latency_s": round(time.perf_counter() - t0, 2),
        "tool_calls": tool_calls,
        "prompt_tokens": prompt_tokens,
        "candidate_tokens": candidate_tokens,
        "total_tokens": prompt_tokens + candidate_tokens,
        "answer": "\n".join(final_text_parts).strip(),
    }


if __name__ == "__main__":
    tb_url = os.environ["TOOLBOX_MCP_V3_URL"]
    sample_q = (
        "Look up James Smith in AWS Postgres, check his support tickets in AWS MySQL, "
        "and retrieve his fraud and churn risk scores from BigQuery ccca."
    )
    res = asyncio.run(run_agent_turn_v3(sample_q, tb_url))
    print("Tools invoked:", res["tool_calls"])
    print(f"Latency: {res['latency_s']}s | Tokens: {res['total_tokens']}")
    print("Answer:\n", res["answer"])
