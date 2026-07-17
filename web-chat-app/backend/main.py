"""
Web Chat Application Backend
FastAPI server that handles chat requests and proxies to DeepSeek API
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import httpx

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load configuration
def load_config() -> dict:
    """Load configuration from environment variables or config.json"""
    config = {
        "deepseekApiKey": os.getenv("DEEPSEEK_API_KEY"),
        "corsOrigin": os.getenv("CORS_ORIGIN", "http://localhost:3000"),
        "deepseekBaseUrl": os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        "requestTimeout": int(os.getenv("REQUEST_TIMEOUT", "30")),
        "maxHistoryMessages": int(os.getenv("MAX_HISTORY_MESSAGES", "20"))
    }
    
    # If API key not in env, try to load from config.json
    if not config["deepseekApiKey"]:
        config_path = Path(__file__).parent / "config.json"
        if config_path.exists():
            try:
                with open(config_path, "r") as f:
                    file_config = json.load(f)
                    config["deepseekApiKey"] = file_config.get("deepseekApiKey")
                    config["corsOrigin"] = file_config.get("corsOrigin", config["corsOrigin"])
                    config["deepseekBaseUrl"] = file_config.get("deepseekBaseUrl", config["deepseekBaseUrl"])
                    config["requestTimeout"] = file_config.get("requestTimeout", config["requestTimeout"])
                    config["maxHistoryMessages"] = file_config.get("maxHistoryMessages", config["maxHistoryMessages"])
            except Exception as e:
                logger.error(f"Failed to load config.json: {e}")
    
    if not config["deepseekApiKey"]:
        logger.error("DEEPSEEK_API_KEY is not set and config.json is missing or has no API key")
        raise RuntimeError("DEEPSEEK_API_KEY is not configured")
    
    return config

# Global config
CONFIG = load_config()

# Create FastAPI app
app = FastAPI(title="Legal Advisor API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[CONFIG["corsOrigin"]],
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["Content-Type"]
)

# Request models
class ChatRequest:
    def __init__(self, message: str, history: Optional[list] = None):
        self.message = message
        self.history = history or []


def validate_chat_request(data: dict) -> tuple[bool, Optional[str]]:
    """Validate chat request data"""
    if not isinstance(data, dict):
        return False, "Invalid JSON"
    
    if "message" not in data:
        return False, "message field is required"
    
    if not isinstance(data["message"], str):
        return False, "message must be a string"
    
    if not data["message"].strip():
        return False, "message cannot be empty"
    
    return True, None


def limit_history(messages: list, max_count: int = 20) -> list:
    """Limit history to most recent N messages"""
    return messages[-max_count:] if messages else []


async def stream_chat_response(message: str, history: list) -> StreamingResponse:
    """Stream chat response from DeepSeek API"""
    
    # Build messages array with system prompt
    messages = [
        {"role": "system", "content": "You are a professional legal advisor assistant. Provide helpful, accurate legal information but always remind users that you are not a substitute for professional legal advice."}
    ]
    
    # Add conversation history
    limited_history = limit_history(history, CONFIG["maxHistoryMessages"])
    for msg in limited_history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    
    # Add current message
    messages.append({"role": "user", "content": message})
    
    # Prepare request to DeepSeek
    url = f"{CONFIG['deepseekBaseUrl']}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {CONFIG['deepseekApiKey']}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek-chat",
        "messages": messages,
        "stream": True
    }
    
    async def generate():
        try:
            async with httpx.AsyncClient(timeout=CONFIG["requestTimeout"]) as client:
                async with client.stream("POST", url, json=payload, headers=headers) as response:
                    if response.status_code == 401:
                        yield 'data: {"error": "Authentication failed: invalid API key"}\n\n'
                        return
                    
                    if response.status_code != 200:
                        yield f'data: {{"error": "Upstream service error: HTTP {response.status_code}"}}\n\n'
                        return
                    
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            data = line[6:]  # Remove "data: " prefix
                            # Transform DeepSeek format to our format
                            if data == "[DONE]":
                                yield 'data: {"content": "", "done": true}\n\n'
                            else:
                                try:
                                    chunk = json.loads(data)
                                    if "choices" in chunk and len(chunk["choices"]) > 0:
                                        delta = chunk["choices"][0].get("delta", {})
                                        content = delta.get("content", "")
                                        finish_reason = chunk["choices"][0].get("finish_reason")
                                        done = finish_reason == "stop"
                                        yield f'data: {{"content": {json.dumps(content)}, "done": {str(done).lower()}}}\n\n'
                                except json.JSONDecodeError:
                                    pass
        except httpx.TimeoutException:
            yield 'data: {"error": "Request timeout"}\n\n'
        except Exception as e:
            logger.error(f"Error streaming response: {e}")
            yield f'data: {{"error": "Internal server error: {str(e)}"}}\n\n'
    
    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "ok", "message": "Legal Advisor API is running"}


@app.post("/api/chat")
async def chat(request: Request):
    """Handle chat requests"""
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    
    # Validate request
    is_valid, error = validate_chat_request(data)
    if not is_valid:
        raise HTTPException(status_code=400, detail=f"Invalid request: {error}")
    
    message = data["message"]
    history = data.get("history", [])
    
    # Stream response
    return await stream_chat_response(message, history)


@app.options("/api/chat")
async def chat_options():
    """Handle CORS preflight requests"""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)