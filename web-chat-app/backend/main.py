"""
Web Chat Application Backend
FastAPI server that handles chat requests using OpenAI Agents SDK with DeepSeek
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

# Agents SDK imports
from agents import Agent, Runner, OpenAIChatCompletionsModel, set_tracing_disabled, function_tool
from openai import AsyncOpenAI

# Disable tracing to avoid requiring OpenAI API key
set_tracing_disabled(disabled=True)

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
        "model": os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"),
        "requestTimeout": int(os.getenv("REQUEST_TIMEOUT", "30")),
        "maxHistoryMessages": int(os.getenv("MAX_HISTORY_MESSAGES", "20"))
    }
    
    # If API key not in env, try to load from config.json
    config_path = Path(__file__).parent / "config.json"
    if config_path.exists():
        try:
            with open(config_path, "r") as f:
                file_config = json.load(f)
                # Only override if not set in env
                if not config["deepseekApiKey"]:
                    config["deepseekApiKey"] = file_config.get("deepseekApiKey")
                config["corsOrigin"] = file_config.get("corsOrigin", config["corsOrigin"])
                config["deepseekBaseUrl"] = file_config.get("deepseekBaseUrl", config["deepseekBaseUrl"])
                config["model"] = file_config.get("model", config["model"])
                config["requestTimeout"] = file_config.get("requestTimeout", config["requestTimeout"])
                config["maxHistoryMessages"] = file_config.get("maxHistoryMessages", config["maxHistoryMessages"])
                # Always read tavilyApiKey from config file
                config["tavilyApiKey"] = file_config.get("tavilyApiKey")
        except Exception as e:
            logger.error(f"Failed to load config.json: {e}")
    
    if not config["deepseekApiKey"]:
        logger.error("DEEPSEEK_API_KEY is not set and config.json is missing or has no API key")
        raise RuntimeError("DEEPSEEK_API_KEY is not configured")
    
    return config

# Global config
CONFIG = load_config()

# Configure DeepSeek client
deepseek_client = AsyncOpenAI(
    api_key=CONFIG["deepseekApiKey"],
    base_url=CONFIG["deepseekBaseUrl"],
)

# Create model instance for Agents SDK
deepseek_model = OpenAIChatCompletionsModel(
    model=CONFIG["model"],
    openai_client=deepseek_client
)


# ============================================================
# Tool Definitions
# ============================================================

@function_tool
def get_legal_reference(law_type: str) -> str:
    logger.info("call get_legal_reference")
    """获取法律条文参考
    
    Args:
        law_type: 法律类型，可选值: contract(合同法), property(物权法), civil(民法典), labor(劳动法), criminal(刑法)
    """
    references = {
        "contract": "《中华人民共和国合同法》第十条：当事人订立合同，有书面形式、口头形式和其他形式。",
        "property": "《中华人民共和国物权法》第六十四条：私人对其合法的收入、房屋、生活用品、生产工具原材料等不动产和动产享有所有权。",
        "civil": "《中华人民共和国民法典》第一百一十九条：依法成立的合同，对当事人具有法律约束力。",
        "labor": "《中华人民共和国劳动法》第十六条：劳动合同是劳动者与用人单位确立劳动关系、明确双方权利和义务的协议。",
        "criminal": "《中华人民共和国刑法》第一条：为了惩罚犯罪，保护人民，根据宪法，结合我国同犯罪作斗争的具体经验及实际情况，制定本法。",
    }
    return references.get(law_type, "未找到相关法律条文")


@function_tool
def search_legal_keyword(keyword: str) -> str:
    logger.info("call search_legal_keyword")
    """根据关键词搜索相关法律条文
    
    Args:
        keyword: 要搜索的法律关键词，如：违约金、侵权、租赁等
    """
    # 简单的关键词匹配示例，实际可以使用更复杂的搜索逻辑
    keyword_map = {
        "违约金": "《民法典》第五百八十五条：当事人可以约定一方违约时应当根据违约情况向对方支付一定数额的违约金，也可以约定因违约产生的损失赔偿额的计算方法。",
        "侵权": "《民法典》第一千一百六十五条：行为人因过错侵害他人民事权益造成损害的，应当承担侵权责任。",
        "租赁": "《民法典》第七百零三条：租赁合同是出租人将租赁物交付承租人使用、收益，承租人支付租金的合同。",
        "离婚": "《民法典》第一千零七十九条：夫妻一方要求离婚的，可以由有关组织进行调解或者直接向人民法院提起离婚诉讼。",
        "继承": "《民法典》第一千一百二十三条：继承开始后，按照法定继承办理；有遗嘱的，按照遗嘱继承或者遗赠办理；有遗赠扶养协议的，按照协议办理。",
        "债务": "《民法典》第六百七十五条：借款人应当按照约定的期限返还借款。对借款期限没有约定或者约定不明确，依据本法第五百一十条的规定仍不能确定的，借款人可以随时返还；贷款人可以催告借款人在合理期限内返还。",
    }
    
    for kw, content in keyword_map.items():
        if kw in keyword:
            return content
    
    return f"未找到与「{keyword}」相关的法律条文。建议您咨询专业律师获取更准确的法律信息。"


@function_tool
def web_search(query: str) -> str:
    logger.info("call web_search")
    """使用 Tavily 搜索互联网获取最新信息
    
    Args:
        query: 搜索查询关键词
    """
    import httpx
    
    tavily_key = CONFIG.get("tavilyApiKey")
    if not tavily_key:
        return "错误：未配置 Tavily API Key"
    
    try:
        response = httpx.post(
            "https://api.tavily.com/search",
            json={
                "api_key": tavily_key,
                "query": query,
                "search_depth": "basic",
                "max_results": 5
            },
            timeout=15.0
        )
        response.raise_for_status()
        data = response.json()
        
        results = data.get("results", [])
        if not results:
            return f"未找到与「{query}」相关的搜索结果"
        
        formatted_results = []
        for i, r in enumerate(results, 1):
            title = r.get("title", "无标题")
            content = r.get("content", "无内容")[:300]
            url = r.get("url", "")
            formatted_results.append(f"{i}. {title}\n   {content}...\n   来源: {url}")
        
        return "搜索结果:\n\n" + "\n\n".join(formatted_results)
    except Exception as e:
        logger.error(f"Web search error: {e}")
        return f"搜索失败: {str(e)}"


# ============================================================
# Agent Definition
# ============================================================

legal_agent = Agent(
    name="法律助手",
    instructions="""你是一个专业的法律顾问助手。

你的职责：
1. 回答用户的法律问题，提供准确的法律信息
2. 当用户询问具体法律条文时，使用 get_legal_reference 或 search_legal_keyword 工具查询
3. 当需要查询最新信息或不在本地知识库中的内容时，使用 web_search 工具搜索互联网
4. 提醒用户这仅供参考，不是正式法律意见

回答要求：
- 语气专业、友好
- 复杂问题建议咨询专业律师
- 如果需要查询特定法律条文，主动使用提供的工具""",
    model=deepseek_model,
    tools=[get_legal_reference, search_legal_keyword, web_search],
)


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


# Valid models
VALID_MODELS = ["deepseek-v4-flash", "deepseek-v4-pro", "deepseek-chat", "deepseek-reasoner"]

# Reasoning effort options
REASONING_EFFORT_OPTIONS = ["high", "max", "low"]


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
    
    # Validate model if provided
    model = data.get("model")
    if model and model not in VALID_MODELS:
        return False, f"Invalid model. Valid models: {', '.join(VALID_MODELS)}"
    
    # Validate reasoning_effort if provided
    reasoning_effort = data.get("reasoning_effort")
    if reasoning_effort and reasoning_effort not in REASONING_EFFORT_OPTIONS:
        return False, f"Invalid reasoning_effort. Valid options: {', '.join(REASONING_EFFORT_OPTIONS)}"
    
    return True, None


def limit_history(messages: list, max_count: int = 20) -> list:
    """Limit history to most recent N messages"""
    return messages[-max_count:] if messages else []


async def stream_chat_response(message: str, history: list, model: str = None, 
                             thinking: bool = True, reasoning_effort: str = "high") -> StreamingResponse:
    """Stream chat response using Agents SDK with DeepSeek"""
    
    async def generate():
        try:
            # Create a fresh agent instance with the selected model if needed
            # For now, use the default agent - model is already set in CONFIG
            agent = legal_agent
            
            # Build context with history for the agent
            # Note: Agents SDK manages history internally via the Agent's instructions
            # We pass the current message along with relevant context
            
            # Run the agent in streaming mode
            result = Runner.run_streamed(agent, message)
            
            # Track tool calls for logging
            tool_calls_log = []
            
            # Stream events from the agent
            async for event in result.stream_events():
                # Handle raw response events (text delta)
                if event.type == "raw_response_event":
                    from openai.types.responses import ResponseTextDeltaEvent
                    if isinstance(event.data, ResponseTextDeltaEvent):
                        content = event.data.delta
                        yield f'data: {{"content": {json.dumps(content)}, "reasoning_content": "", "done": false}}\n\n'
                
                # Handle tool call events - log tool invocation
                elif event.type == "tool_call_event":
                    tool_name = getattr(event, 'tool_name', 'unknown')
                    tool_input = getattr(event, 'input', {})
                    logger.info(f"🔧 工具调用: {tool_name}")
                    logger.info(f"   输入参数: {json.dumps(tool_input, ensure_ascii=False)}")
                    tool_calls_log.append({
                        "tool": tool_name,
                        "input": tool_input,
                        "timestamp": logging.currentframe().f_code.co_name  # Placeholder
                    })
                
                # Handle tool result events - log tool response
                elif event.type == "tool_call_result_event":
                    tool_name = getattr(event, 'tool_name', 'unknown')
                    tool_result = getattr(event, 'result', '')
                    logger.info(f"✅ 工具返回: {tool_name}")
                    logger.info(f"   返回结果: {tool_result[:200]}..." if len(str(tool_result)) > 200 else f"   返回结果: {tool_result}")
                    # Update the log entry with result
                    if tool_calls_log and tool_calls_log[-1].get("tool") == tool_name:
                        tool_calls_log[-1]["result"] = str(tool_result)[:500]
                
                # Handle agent delta events (structured output)
                elif event.type == "agent_delta_event":
                    if hasattr(event, 'delta') and event.delta:
                        # Handle agent response deltas
                        pass
            
            # Log summary of all tool calls after completion
            if tool_calls_log:
                logger.info(f"📊 本次对话工具调用统计: {len(tool_calls_log)} 次")
                for i, call in enumerate(tool_calls_log, 1):
                    logger.info(f"   [{i}] {call['tool']}: {call.get('result', '无返回')[:100]}...")
            
            # Send final message
            yield f'data: {{"content": "", "reasoning_content": "", "done": true}}\n\n'
            
        except Exception as e:
            logger.error(f"Error in agent streaming: {e}")
            import traceback
            traceback.print_exc()
            yield f'data: {{"error": "Agent error: {str(e)}"}}\n\n'
    
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
    model = data.get("model")  # User-selected model
    thinking = data.get("thinking", True)  # Enable thinking by default
    reasoning_effort = data.get("reasoning_effort", "high")  # Default to high reasoning
    
    # Stream response
    return await stream_chat_response(message, history, model, thinking, reasoning_effort)


@app.options("/api/chat")
async def chat_options():
    """Handle CORS preflight requests"""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)