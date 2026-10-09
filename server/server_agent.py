import asyncio
import json
import os
import random
import re
from typing import Any, Dict, Optional
import httpx
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
    or "qwen/qwen3.8-27b"
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
# REAL WEATHER API & TOOLS (OPEN-METEO INTEGRATION)
# ------------------------------------------------------------------
WMO_WEATHER_CODES = {
    0: "Clear Sky",
    1: "Mainly Clear", 2: "Partly Cloudy", 3: "Overcast",
    45: "Foggy", 48: "Depositing Rime Fog",
    51: "Light Drizzle", 53: "Moderate Drizzle", 55: "Dense Drizzle",
    61: "Slight Rain", 63: "Moderate Rain", 65: "Heavy Rain",
    71: "Slight Snow", 73: "Moderate Snow", 75: "Heavy Snow",
    80: "Slight Rain Showers", 81: "Moderate Rain Showers", 82: "Violent Rain Showers",
    95: "Thunderstorm", 96: "Thunderstorm with Slight Hail", 99: "Thunderstorm with Heavy Hail"
}


def get_city_coordinates(city: str) -> Optional[Dict[str, float]]:
    """Geocodes city name to latitude and longitude using Open-Meteo Geocoding API."""
    try:
        url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1&language=en&format=json"
        response = httpx.get(url, timeout=10.0)
        response.raise_for_status()
        data = response.json()
        if data.get("results"):
            location = data["results"][0]
            return {
                "latitude": location["latitude"],
                "longitude": location["longitude"],
                "name": location.get("name", city),
                "country": location.get("country", ""),
            }
    except Exception as e:
        print(f"⚠️ Geocoding error for '{city}': {e}")
    return None


def get_weather(city: str) -> Dict[str, Any]:
    """Fetches REAL current weather for a city using Open-Meteo API."""
    coords = get_city_coordinates(city)
    if not coords:
        # Fallback to simulated weather if geocoding yields no results
        return {
            "city": city.title(),
            "temperature": "22°C",
            "condition": "Partly Cloudy",
            "humidity": "55%",
            "wind_speed": "12 km/h",
            "source": "Fallback Generator",
        }

    try:
        lat, lon = coords["latitude"], coords["longitude"]
        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={lat}&longitude={lon}&current_weather=true&hourly=relative_humidity_2m"
        )
        response = httpx.get(url, timeout=10.0)
        response.raise_for_status()
        data = response.json()
        current = data.get("current_weather", {})

        weather_code = current.get("weathercode", 0)
        condition = WMO_WEATHER_CODES.get(weather_code, "Partly Cloudy")
        temp = current.get("temperature", 22)
        wind = current.get("windspeed", 10)
        
        humidity_list = data.get("hourly", {}).get("relative_humidity_2m", [])
        humidity = f"{humidity_list[0]}%" if humidity_list else "60%"

        return {
            "city": coords["name"],
            "country": coords["country"],
            "temperature": f"{temp}°C",
            "condition": condition,
            "humidity": humidity,
            "wind_speed": f"{wind} km/h",
            "source": "Open-Meteo Live API",
        }
    except Exception as e:
        print(f"⚠️ Open-Meteo API error for '{city}': {e}")
        return {
            "city": city.title(),
            "temperature": "22°C",
            "condition": "Partly Cloudy",
            "humidity": "55%",
            "wind_speed": "12 km/h",
            "source": "Fallback Generator",
        }


def get_forecast(city: str, days: int = 3) -> Dict[str, Any]:
    """Fetches REAL multi-day weather forecast using Open-Meteo API."""
    days = min(max(1, days), 7)
    coords = get_city_coordinates(city)
    if not coords:
        return {"city": city.title(), "days": days, "forecast": [], "source": "Fallback Generator"}

    try:
        lat, lon = coords["latitude"], coords["longitude"]
        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={lat}&longitude={lon}&daily=weathercode,temperature_2m_max,temperature_2m_min&timezone=auto"
        )
        response = httpx.get(url, timeout=10.0)
        response.raise_for_status()
        data = response.json()
        daily = data.get("daily", {})

        times = daily.get("time", [])
        max_temps = daily.get("temperature_2m_max", [])
        codes = daily.get("weathercode", [])

        forecasts = []
        for i in range(min(days, len(times))):
            forecasts.append({
                "date": times[i],
                "temperature_max": f"{max_temps[i]}°C",
                "condition": WMO_WEATHER_CODES.get(codes[i], "Partly Cloudy"),
            })

        return {
            "city": coords["name"],
            "country": coords["country"],
            "days": days,
            "forecast": forecasts,
            "source": "Open-Meteo Live API",
        }
    except Exception as e:
        print(f"⚠️ Forecast error for '{city}': {e}")
        return {"city": city.title(), "days": days, "forecast": [], "source": "Fallback Generator"}


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
    Receives user query, executes weather tools, reasons using LLM,
    and returns a full structured Agent-to-Agent JSON completion payload.
    """
    # 1. Infer city if not provided
    if not city:
        match = re.search(r"in\s+([A-Za-z\s]+)", query, re.IGNORECASE)
        if match:
            city = match.group(1).strip()
        else:
            city = "Bangalore"

    # 2. Execute real weather tool
    weather_data = get_weather(city)

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
        "tool_executed": "get_weather",
        "weather_data": weather_data,
        "agent_reasoning": llm_output.get("response") or llm_output.get("error_details"),
        "model_used": model_name,
    }


# Registry of available JSON-RPC methods
RPC_METHODS = {
    "get_weather": get_weather,
    "get_forecast": get_forecast,
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
        
        weather_result = await asyncio.to_thread(get_weather, city_name)
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