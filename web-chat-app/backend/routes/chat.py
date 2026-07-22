"""API 路由模块 - 聊天接口"""
import json
import logging
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from agents import Agent, Runner

from config import config
from agent import create_legal_agent

logger = logging.getLogger(__name__)

# 创建路由
router = APIRouter()

# 有效模型列表
VALID_MODELS = ["deepseek-v4-flash", "deepseek-v4-pro", "deepseek-chat", "deepseek-reasoner"]

# Reasoning effort 选项
REASONING_EFFORT_OPTIONS = ["high", "max", "low"]


def validate_chat_request(data: dict) -> tuple[bool, Optional[str]]:
    """验证聊天请求数据
    
    Args:
        data: 请求 JSON 数据
    
    Returns:
        (是否有效, 错误信息)
    """
    if not isinstance(data, dict):
        return False, "Invalid JSON"
    
    if "message" not in data:
        return False, "message field is required"
    
    if not isinstance(data["message"], str):
        return False, "message must be a string"
    
    if not data["message"].strip():
        return False, "message cannot be empty"
    
    # 验证模型
    model = data.get("model")
    if model and model not in VALID_MODELS:
        return False, f"Invalid model. Valid models: {', '.join(VALID_MODELS)}"
    
    # 验证 reasoning_effort
    reasoning_effort = data.get("reasoning_effort")
    if reasoning_effort and reasoning_effort not in REASONING_EFFORT_OPTIONS:
        return False, f"Invalid reasoning_effort. Valid options: {', '.join(REASONING_EFFORT_OPTIONS)}"
    
    return True, None


def limit_history(messages: List[dict], max_count: int = 20) -> List[dict]:
    """限制历史消息数量
    
    Args:
        messages: 消息列表
        max_count: 最大消息数量
    
    Returns:
        截断后的消息列表
    """
    return messages[-max_count:] if messages else []


async def stream_chat_response(
    message: str,
    history: List[dict],
    model: Optional[str] = None,
    thinking: bool = True,
    reasoning_effort: str = "high"
) -> StreamingResponse:
    """流式返回聊天响应
    
    Args:
        message: 用户消息
        history: 历史消息
        model: 选择的模型
        thinking: 是否启用思考
        reasoning_effort: 思考深度
    
    Returns:
        SSE 流式响应
    """
    
    async def generate():
        try:
            # 根据选择的模型创建 Agent
            if model and model != config.model:
                agent_model = config.get_model(model)
                agent = create_legal_agent(agent_model)
            else:
                agent = create_legal_agent()
            
            # 将历史消息转换为 Agent 期望的格式
            input_messages = []
            for msg in history:
                input_messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")
                })
            # 添加当前用户消息
            input_messages.append({"role": "user", "content": message})
            
            # 运行 Agent，传入历史消息
            result = Runner.run_streamed(agent, input_messages)
            
            # 记录工具调用
            tool_calls_log = []
            
            # 流式处理事件
            async for event in result.stream_events():
                if event.type == "raw_response_event":
                    from openai.types.responses import ResponseTextDeltaEvent
                    if isinstance(event.data, ResponseTextDeltaEvent):
                        content = event.data.delta
                        yield f'data: {{"content": {json.dumps(content)}, "reasoning_content": "", "done": false}}\n\n'
                
                elif event.type == "tool_call_event":
                    tool_name = getattr(event, 'tool_name', 'unknown')
                    tool_input = getattr(event, 'input', {})
                    logger.info(f"🔧 工具调用: {tool_name}")
                    logger.info(f"   输入参数: {json.dumps(tool_input, ensure_ascii=False)}")
                    tool_calls_log.append({
                        "tool": tool_name,
                        "input": tool_input
                    })
                
                elif event.type == "tool_call_result_event":
                    tool_name = getattr(event, 'tool_name', 'unknown')
                    tool_result = getattr(event, 'result', '')
                    logger.info(f"✅ 工具返回: {tool_name}")
                    logger.info(f"   返回结果: {tool_result[:200]}..." if len(str(tool_result)) > 200 else f"   返回结果: {tool_result}")
                    if tool_calls_log and tool_calls_log[-1].get("tool") == tool_name:
                        tool_calls_log[-1]["result"] = str(tool_result)[:500]
                
                elif event.type == "agent_delta_event":
                    # 处理 Agent 响应增量
                    pass
            
            # 记录工具调用统计
            if tool_calls_log:
                logger.info(f"📊 本次对话工具调用统计: {len(tool_calls_log)} 次")
                for i, call in enumerate(tool_calls_log, 1):
                    logger.info(f"   [{i}] {call['tool']}: {call.get('result', '无返回')[:100]}...")
            
            # 发送完成信号
            yield f'data: {{"content": "", "reasoning_content": "", "done": true}}\n\n'
            
        except Exception as e:
            logger.error(f"Error in agent streaming: {e}")
            import traceback
            traceback.print_exc()
            yield f'data: {{"error": "Agent error: {str(e)}"}}\n\n'
    
    return StreamingResponse(generate(), media_type="text/event-stream")


@router.get("/")
async def root():
    """健康检查"""
    return {"status": "ok", "message": "Legal Advisor API is running"}


@router.post("/api/chat")
async def chat(request: Request) -> StreamingResponse:
    """处理聊天请求
    
    Args:
        request: FastAPI 请求对象
    
    Returns:
        流式响应
    """
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    
    # 验证请求
    is_valid, error = validate_chat_request(data)
    if not is_valid:
        raise HTTPException(status_code=400, detail=f"Invalid request: {error}")
    
    message = data["message"]
    history = data.get("history", [])
    model = data.get("model")
    thinking = data.get("thinking", True)
    reasoning_effort = data.get("reasoning_effort", "high")
    
    # 流式响应
    return await stream_chat_response(message, history, model, thinking, reasoning_effort)


@router.options("/api/chat")
async def chat_options():
    """处理 CORS 预检请求"""
    return {"status": "ok"}