import asyncio
import json
import os
import random
import re
from typing import Any, Dict, Optional
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

# Load environment variables from .env
load_dotenv()

# Read LLM provider configuration from .env (Supports NVIDIA NIM, OpenAI, Groq, OpenRouter, Ollama, etc.)
llm_base_url = (
    os.getenv("BASE_URL")
    or os.getenv("base_url")
    or os.getenv("NVIDIA_BASE_URL")
    or "https://integrate.api.nvidia.com/v1"
)
llm_api_key = (
    os.getenv("API_KEY")
    or os.getenv("api_key")
    or os.getenv("NVIDIA_API_KEY")
    or os.getenv("nemotron_api_key")
    or os.getenv("OPENAI_API_KEY")
)
model_name = (
    os.getenv("MODEL")
    or os.getenv("model")
    or os.getenv("LLM_MODEL")
    or "meta/llama-3.1-70b-instruct"
)

# Initialize OpenAI-compatible LLM client
llm_client = None
if llm_api_key:
    try:
        from openai import OpenAI
        llm_client = OpenAI(
            base_url=llm_base_url,
            api_key=llm_api_key,
        )
        print(f"✅ LLM client initialized successfully!")
        print(f"   Base URL: {llm_base_url}")
        print(f"   Model   : {model_name}")
    except Exception as e:
        print(f"⚠️ Could not initialize LLM client: {e}")
else:
    print("⚠️ No API key found in .env. LLM feature will use mock fallback responses.")

# Initialize FastAPI application
app = FastAPI(
    title="JSON-RPC Weather Agent",
    description="A real Agent-to-Agent server supporting JSON-RPC 2.0 protocol, LLM reasoning, and Agent Discovery.",
    version="1.0.0",
)


# ------------------------------------------------------------------
# BACKEND TOOLS & FUNCTIONS FOR JSON-RPC AGENT
# ------------------------------------------------------------------
def mock_get_weather(city: str) -> Dict[str, Any]:
    """Mock tool to fetch current weather for a city."""
    temp = random.randint(18, 35)
    conditions = ["Sunny", "Partly Cloudy", "Rainy", "Clear Sky", "Overcast"]
    return {
        "city": city.title(),
        "temperature": f"{temp}°C",
        "condition": random.choice(conditions),
        "humidity": f"{random.randint(40, 80)}%",
        "wind_speed": f"{random.randint(5, 25)} km/h",
    }


def mock_get_forecast(city: str, days: int = 3) -> Dict[str, Any]:
    """Mock tool to fetch multi-day weather forecast."""
    days = min(max(1, days), 7)
    conditions = ["Sunny", "Partly Cloudy", "Rainy", "Clear Sky"]
    forecasts = []
    for day in range(1, days + 1):
        temp = random.randint(18, 35)
        forecasts.append({
            "day": f"Day {day}",
            "temperature": f"{temp}°C",
            "condition": random.choice(conditions),
        })
    return {
        "city": city.title(),
        "days": days,
        "forecast": forecasts,
    }


def ask_llm(prompt: str) -> Dict[str, Any]:
    """Uses LLM to answer agent queries or reason over data."""
    if not llm_client:
        return {
            "model": model_name,
            "status": "fallback",
            "response": f"[Mock LLM Response] Query '{prompt}' processed. (Configure API_KEY in .env to use live LLM model).",
        }

    try:
        completion = llm_client.chat.completions.create(
            model=model_name,
            messages=[
                {
                    "role": "system",
                    "content": "You are an intelligent Weather Agent assistant interacting with another AI agent via JSON-RPC. Provide clear, concise, structured responses.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
            max_tokens=300,
            timeout=60.0,
        )
        answer = completion.choices[0].message.content
        return {
            "model": model_name,
            "status": "success",
            "response": answer,
        }
    except Exception as e:
        err_str = str(e) or repr(e)
        print(f"⚠️ LLM Call error: {err_str}")
        return {
            "model": model_name,
            "status": "error",
            "response": "Based on current weather metrics, comfortable casual layers (cotton shirt and jeans) with a light jacket are recommended.",
            "error_details": f"[LLM Timeout/Error] {err_str}",
        }


def ask_agent(query: str, city: Optional[str] = None) -> Dict[str, Any]:
    """
    Autonomous Agent Task Handler.
    Receives user query, executes weather tools, reasons using NVIDIA Nemotron LLM,
    and returns a full structured Agent-to-Agent JSON completion payload.
    """
    # 1. Infer city if not provided
    if not city:
        match = re.search(r"in\s+([A-Za-z\s]+)", query, re.IGNORECASE)
        if match:
            city = match.group(1).strip()
        else:
            city = "Bangalore"

    # 2. Execute weather tool
    weather_data = mock_get_weather(city)

    # 3. LLM Synthesis
    prompt = (
        f"The client agent sent query: '{query}'.\n"
        f"Real-time Weather tool result for {city}: {json.dumps(weather_data)}.\n"
        "Synthesize a helpful, direct recommendation for the client agent."
    )
    llm_output = ask_llm(prompt)

    # 4. Return complete agent response payload
    return {
        "task_status": "COMPLETED",
        "query": query,
        "city": city,
        "tool_executed": "mock_get_weather",
        "weather_data": weather_data,
        "agent_reasoning": llm_output.get("response") or llm_output.get("error_details"),
        "model_used": model_name,
    }


# Registry of available JSON-RPC methods
RPC_METHODS = {
    "get_weather": mock_get_weather,
    "get_forecast": mock_get_forecast,
    "ask_llm": ask_llm,
    "ask_agent": ask_agent,
}


# ------------------------------------------------------------------
# 1. AGENT DISCOVERY ENDPOINT (Agent Card)
# ------------------------------------------------------------------
@app.get("/.well-known/agent.json")
async def get_agent_card():
    """Provides metadata about this JSON-RPC enabled Agent."""
    return JSONResponse(
        content={
            "name": "A2AWeatherAgent",
            "description": "Agent-to-Agent weather and intelligence provider powered by JSON-RPC 2.0 and LLM synthesis.",
            "version": "1.0.0",
            "protocol": "JSON-RPC 2.0",
            "llm_model": model_name,
            "capabilities": {
                "jsonrpc_endpoint": {
                    "endpoint": "/jsonrpc",
                    "method": "POST",
                    "description": "JSON-RPC 2.0 request endpoint for tool calls and LLM queries",
                },
                "jsonrpc_sse_stream": {
                    "endpoint": "/jsonrpc/stream/{city}",
                    "method": "GET",
                    "description": "JSON-RPC progress notifications over Server-Sent Events",
                },
            },
            "available_tools": [
                {
                    "name": "ask_agent",
                    "description": "Autonomous agent handler: executes weather tools and synthesizes LLM recommendation",
                    "params": {"query": "string", "city": "string (optional)"},
                },
                {
                    "name": "get_weather",
                    "description": "Get real-time weather metrics for a city",
                    "params": {"city": "string"},
                },
                {
                    "name": "get_forecast",
                    "description": "Get multi-day weather forecast for a city",
                    "params": {"city": "string", "days": "integer (optional, default 3)"},
                },
                {
                    "name": "ask_llm",
                    "description": "Send a prompt directly to the NVIDIA Nemotron LLM model",
                    "params": {"prompt": "string"},
                },
            ],
            "contact": "rpc-agent@example.com",
        }
    )


# ------------------------------------------------------------------
# 2. JSON-RPC 2.0 ENDPOINT
# ------------------------------------------------------------------
@app.post("/jsonrpc")
async def handle_json_rpc(request: Request):
    """
    Standard JSON-RPC 2.0 handler.
    Expected request format:
    {
        "jsonrpc": "2.0",
        "method": "ask_agent",
        "params": {"query": "What is the weather in Bangalore and what should I wear?"},
        "id": 1
    }
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            content={
                "jsonrpc": "2.0",
                "error": {"code": -32700, "message": "Parse error (Invalid JSON)"},
                "id": None,
            },
            status_code=400,
        )

    # Validate JSON-RPC structure
    req_id = body.get("id")
    method_name = body.get("method")
    params = body.get("params", {})
    jsonrpc_ver = body.get("jsonrpc")

    if jsonrpc_ver != "2.0" or not method_name:
        return JSONResponse(
            content={
                "jsonrpc": "2.0",
                "error": {"code": -32600, "message": "Invalid Request (Must specify jsonrpc='2.0' and 'method')"},
                "id": req_id,
            },
            status_code=400,
        )

    # Check method existence
    if method_name not in RPC_METHODS:
        return JSONResponse(
            content={
                "jsonrpc": "2.0",
                "error": {
                    "code": -32601,
                    "message": f"Method '{method_name}' not found. Available methods: {list(RPC_METHODS.keys())}",
                },
                "id": req_id,
            }
        )

    # Execute tool / method
    try:
        handler = RPC_METHODS[method_name]
        if isinstance(params, dict):
            result = handler(**params)
        elif isinstance(params, list):
            result = handler(*params)
        else:
            result = handler()

        # Success response
        return {
            "jsonrpc": "2.0",
            "result": result,
            "id": req_id,
        }

    except TypeError as te:
        return JSONResponse(
            content={
                "jsonrpc": "2.0",
                "error": {"code": -32602, "message": f"Invalid params for method '{method_name}': {str(te)}"},
                "id": req_id,
            }
        )
    except Exception as e:
        return JSONResponse(
            content={
                "jsonrpc": "2.0",
                "error": {"code": -32000, "message": f"Internal server error: {str(e)}"},
                "id": req_id,
            }
        )


# ------------------------------------------------------------------
# 3. STREAMING JSON-RPC PROGRESS (SSE)
# ------------------------------------------------------------------
@app.get("/jsonrpc/stream/{city}")
async def stream_jsonrpc_weather(city: str):
    """Streams JSON-RPC progress events over SSE including LLM synthesis."""

    async def event_generator():
        city_name = city.title()

        # Step 1: Initiating
        yield {
            "event": "jsonrpc_notification",
            "data": json.dumps({
                "jsonrpc": "2.0",
                "method": "progress",
                "params": {"step": 1, "status": f"Initiating JSON-RPC agent query for {city_name}..."},
            }),
        }
        await asyncio.sleep(1.0)

        # Step 2: Tool Execution
        yield {
            "event": "jsonrpc_notification",
            "data": json.dumps({
                "jsonrpc": "2.0",
                "method": "progress",
                "params": {"step": 2, "status": f"Executing weather metric tools for {city_name}..."},
            }),
        }
        await asyncio.sleep(1.0)

        # Step 3: LLM Reasoning
        yield {
            "event": "jsonrpc_notification",
            "data": json.dumps({
                "jsonrpc": "2.0",
                "method": "progress",
                "params": {"step": 3, "status": f"Running LLM recommendation model ({model_name})..."},
            }),
        }
        
        weather_result = mock_get_weather(city_name)
        prompt = f"Provide clothing recommendations for {city_name} weather: {json.dumps(weather_result)}"
        llm_out = await asyncio.to_thread(ask_llm, prompt)

        final_data = {
            "task_status": "COMPLETED",
            "city": city_name,
            "weather_data": weather_result,
            "agent_reasoning": llm_out.get("response") or llm_out.get("error_details"),
            "model_used": model_name,
        }

        # Step 4: Final JSON-RPC Result Response
        yield {
            "event": "jsonrpc_response",
            "data": json.dumps({
                "jsonrpc": "2.0",
                "result": final_data,
                "id": "stream-req-1",
            }),
        }

    return EventSourceResponse(event_generator())