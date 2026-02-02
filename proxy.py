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
        result = subprocess.run(
            ["gcloud", "auth", "application-default", "print-access-token"],
            capture_output=True,
            text=True,
            check=True
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

            # Return response
            return JSONResponse(
                content=vertex_response.json(),
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
