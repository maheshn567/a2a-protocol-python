import asyncio
import json
import os
import re
import sys
import httpx
from dotenv import load_dotenv

# Load environment credentials from .env
load_dotenv()

SERVER_URL = "http://localhost:8000"

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

# Initialize Client LLM Agent
client_llm = None
if llm_api_key:
    try:
        from openai import OpenAI
        client_llm = OpenAI(
            base_url=llm_base_url,
            api_key=llm_api_key,
        )
        print(f"🤖 [CLIENT AGENT] Initialized with LLM model '{model_name}'.")
    except Exception as e:
        print(f"⚠️ [CLIENT AGENT] Could not initialize LLM client: {e}")
else:
    print("⚠️ [CLIENT AGENT] No API key found in .env. Will fall back to default agent choices.")


# ------------------------------------------------------------------
# SERVER STREAMING COMMUNICATION HELPERS
# ------------------------------------------------------------------
async def discover_server_agent(http_client: httpx.AsyncClient) -> dict:
    """Discovers the Server Agent capabilities by fetching the Agent Card."""
    url = f"{SERVER_URL}/.well-known/agent.json"
    print(f"🔍 [CLIENT AGENT] Discovering Server Agent at {url}...")
    try:
        response = await http_client.get(url)
        response.raise_for_status()
        agent_card = response.json()
        print("✅ [CLIENT AGENT] Agent Discovery successful.")
        return agent_card
    except Exception as e:
        print(f"❌ [CLIENT AGENT] Agent Discovery failed: {e}")
        return {}


async def call_server_stream_rpc(http_client: httpx.AsyncClient, city: str) -> dict:
    """
    Connects ONLY to the Response Streaming Endpoint (/jsonrpc/stream/{city}).
    Streams real-time JSON-RPC progress notifications over SSE and returns the final JSON-RPC payload.
    """
    url = f"{SERVER_URL}/jsonrpc/stream/{city}"
    print(f"\n📡 [CLIENT AGENT -> SERVER AGENT] Connecting ONLY to Response Streaming Endpoint:")
    print(f"   GET {url}")
    print("\n⏳ Both Client and Server Agents are awaiting stream completion...\n")

    final_response = {"jsonrpc": "2.0", "result": {}, "id": "stream-req-1"}

    try:
        async with http_client.stream("GET", url, timeout=httpx.Timeout(60.0, read=None)) as response:
            response.raise_for_status()
            current_event = None
            
            async for line in response.aiter_lines():
                line = line.strip()
                if not line:
                    continue
                
                if line.startswith("event:"):
                    current_event = line[len("event:"):].strip()
                elif line.startswith("data:"):
                    data_str = line[len("data:"):].strip()
                    try:
                        payload = json.loads(data_str)
                    except json.JSONDecodeError:
                        payload = data_str
                    
                    if current_event == "jsonrpc_notification":
                        params = payload.get("params", {})
                        step = params.get("step", "?")
                        status = params.get("status", "")
                        print(f"⏳ [Stream Notification - Step {step}] {status}")

                    elif current_event in ("jsonrpc_response", "complete"):
                        print(f"\n📥 [SERVER AGENT -> CLIENT AGENT] Stream Finished! Final Payload Received:")
                        print(json.dumps(payload, indent=2))
                        final_response = payload

        return final_response

    except Exception as e:
        err_msg = str(e) or repr(e)
        print(f"❌ [CLIENT AGENT] Streaming request failed: {err_msg}")
        return {"jsonrpc": "2.0", "error": {"code": -32000, "message": err_msg}, "id": 1}


# ------------------------------------------------------------------
# BEAUTIFUL LOG RENDERER (TARGET FOR EXEC)
# ------------------------------------------------------------------
def display_beautiful_log(query: str, city: str, rpc_response: dict):
    """Render formatted telemetry and completion logs (invoked dynamically via exec)."""
    print("\n" + "═" * 70)
    print("🎨 BEAUTIFUL A2A STREAMING EXECUTION LOG (RENDERED VIA EXEC)")
    print("═" * 70)
    print(f"📋 Original User Query : \"{query}\"")
    print(f"📡 Endpoint Called     : GET /jsonrpc/stream/{city}")
    
    if "result" in rpc_response:
        res = rpc_response["result"]
        print(f"📌 Stream Status        : ✅ COMPLETED")
        print(f"🏙️ Target City          : {res.get('city') or city}")
        
        if "weather_data" in res:
            w = res["weather_data"]
            print("🌡️ Weather Metrics      :")
            print(f"   • Temperature       : {w.get('temperature')}")
            print(f"   • Condition         : {w.get('condition')}")
            print(f"   • Humidity          : {w.get('humidity')}")
            print(f"   • Wind Speed        : {w.get('wind_speed')}")
        elif "temperature" in res:
            print("🌡️ Weather Metrics      :")
            print(f"   • Temperature       : {res.get('temperature')}")
            print(f"   • Condition         : {res.get('condition')}")
            print(f"   • Humidity          : {res.get('humidity')}")
            print(f"   • Wind Speed        : {res.get('wind_speed')}")
        
        if "agent_reasoning" in res:
            print("\n💡 SERVER AGENT REASONING & AI RECOMMENDATION:")
            print(f"   {res['agent_reasoning']}")
        elif "response" in res:
            print("\n💡 SERVER LLM RESPONSE:")
            print(f"   {res['response']}")
            
    elif "error" in rpc_response:
        err = rpc_response["error"]
        print(f"❌ [AGENT ERROR] Code {err.get('code')}: {err.get('message')}")
        
    print("═" * 70 + "\n")


# ------------------------------------------------------------------
# AUTONOMOUS CLIENT AGENT RUNTIME
# ------------------------------------------------------------------
async def run_client_agent(user_query: str):
    """
    Main Autonomous Client Agent workflow calling ONLY the Response Streaming Endpoint:
    1. Discovers Server Agent Card.
    2. Uses Client LLM to deduce target city from query.
    3. Uses exec() to dynamically execute the stream call function (call_server_stream_rpc).
    4. Uses exec() to dynamically execute the display_beautiful_log renderer.
    """
    print("\n" + "═" * 70)
    print("🤖 AUTONOMOUS CLIENT AGENT INITIALIZING (RESPONSE STREAMING MODE ONLY)")
    print("═" * 70)
    print(f"💬 User Request: \"{user_query}\"")

    async with httpx.AsyncClient(timeout=30.0) as http_client:
        # Step 1: Discover Server Agent
        agent_card = await discover_server_agent(http_client)
        
        # Step 2: Use Client LLM to infer city parameter from user query
        city = "Bangalore"
        if client_llm:
            sys_prompt = (
                "You are an autonomous Client Agent calling a Weather Agent streaming endpoint.\n"
                "Extract the target city name from the user's query.\n"
                "Return a JSON object with one key: 'city': string (e.g. 'Bangalore', 'Tokyo', 'London').\n"
                "Only return pure JSON, no markdown formatting."
            )
            try:
                print("\n🧠 [CLIENT AGENT LLM] Reasoning over user query to extract city...")
                completion = client_llm.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": sys_prompt},
                        {"role": "user", "content": user_query},
                    ],
                    temperature=0.1,
                    max_tokens=50,
                    timeout=30.0,
                )
                raw_llm_res = completion.choices[0].message.content.strip()
                clean_json = re.sub(r"^```json|```$", "", raw_llm_res, flags=re.MULTILINE).strip()
                decision = json.loads(clean_json)
                city = decision.get("city", "Bangalore")
                print(f"🎯 [CLIENT AGENT LLM DECISION] Extracted Target City: '{city}'")
            except Exception as e:
                # Clean single-word city extraction regex fallback
                match = re.search(r"\bin\s+([A-Za-z]+)\b", user_query, re.IGNORECASE)
                if match:
                    city = match.group(1).strip()
                print(f"⚠️ LLM city extraction fallback -> '{city}': {e}")

        # Step 3: Execute ONLY the Response Streaming Endpoint via exec()
        print("\n⚡ [EXEC ENGINE] Executing streaming request ONLY via exec()...")
        exec_request_code = """
async def execute_stream_call():
    return await call_server_stream_rpc(http_client, city)
"""
        exec_scope = {
            "call_server_stream_rpc": call_server_stream_rpc,
            "http_client": http_client,
            "city": city,
        }
        exec(exec_request_code, exec_scope)
        rpc_response = await exec_scope["execute_stream_call"]()

        # Step 4: Execute the display log function dynamically via exec()
        print("\n⚡ [EXEC ENGINE] Executing display and log renderer via exec()...")
        exec_display_code = "display_beautiful_log(user_query, city, rpc_response)"
        display_scope = {
            "display_beautiful_log": display_beautiful_log,
            "user_query": user_query,
            "city": city,
            "rpc_response": rpc_response,
        }
        exec(exec_display_code, display_scope)


def print_usage():
    print("Usage: python client/client.py \"<user query>\"")
    print("Example: python client/client.py \"What is the weather in Bangalore and what should I wear?\"")


async def main():
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)

    query = " ".join(sys.argv[1:])
    await run_client_agent(query)


if __name__ == "__main__":
    asyncio.run(main())
