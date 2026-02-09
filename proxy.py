#!/usr/bin/env python3
"""
Vertex AI Reasoning Proxy
Routes OpenClaw requests to Vertex AI with dynamic reasoning_effort based on model ID.
"""

import os
import json
import subprocess
from typing import Dict, Any
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
import httpx
import uvicorn
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI(title="Vertex AI Reasoning Proxy")

# Configuration
VERTEX_AI_PROJECT = os.getenv("VERTEX_AI_PROJECT", "gen-lang-client-0041139433")
VERTEX_AI_REGION = os.getenv("VERTEX_AI_REGION", "us-west1")
VERTEX_AI_BASE_URL = f"https://{VERTEX_AI_REGION}-aiplatform.googleapis.com/v1/projects/{VERTEX_AI_PROJECT}/locations/{VERTEX_AI_REGION}/endpoints/openapi"
PROXY_HOST = os.getenv("PROXY_HOST", "127.0.0.1")
PROXY_PORT = int(os.getenv("PROXY_PORT", "8000"))

# Model routing: suffix -> reasoning_effort mapping
# Maps to thinking budgets: low=1K, medium=8K, high=24K
REASONING_LEVELS = {
    "low": "low",
    "medium": "medium",
    "high": "high"
}


def get_vertex_token() -> str:
    """Get fresh Vertex AI access token using gcloud."""
    try:
        # Clear GOOGLE_APPLICATION_CREDENTIALS to use default ADC
        env = os.environ.copy()
        env.pop('GOOGLE_APPLICATION_CREDENTIALS', None)

        result = subprocess.run(
            ["gcloud", "auth", "application-default", "print-access-token"],
            capture_output=True,
            text=True,
            check=True,
            env=env
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Failed to get access token: {e}")


def parse_model_id(model_id: str) -> tuple[str, str]:
    """
    Parse model ID to extract base model and reasoning effort.

    Examples:
        google/gemini-2.5-flash-low -> (google/gemini-2.5-flash, low)
        google/gemini-2.5-flash-medium -> (google/gemini-2.5-flash, medium)
        google/gemini-2.5-flash-high -> (google/gemini-2.5-flash, high)
        google/gemini-2.5-flash -> (google/gemini-2.5-flash, medium) [default]
    """
    for suffix, effort in REASONING_LEVELS.items():
        if model_id.endswith(f"-{suffix}"):
            base_model = model_id.rsplit(f"-{suffix}", 1)[0]
            return base_model, effort

    # Default to medium if no suffix
    return model_id, "medium"


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """
    OpenAI-compatible chat completions endpoint.
    Routes to Vertex AI with dynamic reasoning_effort.
    """
    try:
        # Parse incoming request
        body = await request.json()

        # Extract and parse model ID
        model_id = body.get("model", "")
        base_model, reasoning_effort = parse_model_id(model_id)

        # Get fresh token
        token = get_vertex_token()

        # Modify request body
        vertex_body = body.copy()
        vertex_body["model"] = base_model
        vertex_body["reasoning_effort"] = reasoning_effort

        # Log all unique roles before transformation
        if "messages" in vertex_body:
            roles_found = set(msg.get("role") for msg in vertex_body["messages"] if "role" in msg)
            print(f"[DEBUG] Roles in request: {sorted(roles_found)}")

        # Transform unsupported roles for Vertex AI compatibility
        # Vertex AI only supports: system, user, assistant
        if "messages" in vertex_body:
            for msg in vertex_body["messages"]:
                role = msg.get("role")
                if role == "developer":
                    # OpenAI's developer role (for reasoning models) → system
                    msg["role"] = "system"
                    print(f"[TRANSFORM] developer → system")
                elif role == "tool":
                    # Tool results - keep as-is, test if Vertex AI supports it
                    pass
                elif role not in ["system", "user", "assistant", "tool"]:
                    # Any other custom role → system
                    print(f"[TRANSFORM] {role} → system")
                    msg["role"] = "system"

        # Log the request for debugging
        print(f"[PROXY] Model ID: {model_id} → Base: {base_model}, Reasoning: {reasoning_effort}")

        # Forward to Vertex AI
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient(timeout=300.0) as client:
            vertex_response = await client.post(
                f"{VERTEX_AI_BASE_URL}/chat/completions",
                json=vertex_body,
                headers=headers
            )

            # Get response content
            response_content = vertex_response.json()

            # Log errors for debugging
            if vertex_response.status_code >= 400:
                print(f"[ERROR] Vertex AI returned {vertex_response.status_code}")
                print(f"[ERROR] Response: {response_content}")

            # Log detailed response for debugging unexpected_tool_call errors
            if "choices" in response_content and len(response_content["choices"]) > 0:
                choice = response_content["choices"][0]
                finish_reason = choice.get("finish_reason", "unknown")
                message = choice.get("message", {})

                print(f"[RESPONSE] Finish reason: {finish_reason}")

                # Log tool calls if present
                if "tool_calls" in message and message["tool_calls"]:
                    print(f"[RESPONSE] Tool calls: {len(message['tool_calls'])}")
                    for idx, tc in enumerate(message["tool_calls"]):
                        fn_name = tc.get("function", {}).get("name", "unknown")
                        print(f"[RESPONSE]   Tool #{idx}: {fn_name}")

            # Return response
            return JSONResponse(
                content=response_content,
                status_code=vertex_response.status_code
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "vertexai-reasoning-proxy",
        "vertex_ai_project": VERTEX_AI_PROJECT,
        "vertex_ai_region": VERTEX_AI_REGION
    }


@app.get("/")
async def root():
    """Root endpoint with service info."""
    return {
        "service": "Vertex AI Reasoning Proxy",
        "version": "1.0.0",
        "endpoints": {
            "chat_completions": "/v1/chat/completions",
            "health": "/health"
        },
        "reasoning_levels": REASONING_LEVELS
    }


if __name__ == "__main__":
    uvicorn.run(
        app,
        host=PROXY_HOST,
        port=PROXY_PORT,
        log_level="info"
    )
