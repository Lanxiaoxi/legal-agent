"""Agent 定义模块"""
import logging
from typing import Optional

from agents import Agent, OpenAIChatCompletionsModel

from config import config
from tools import TOOLS

logger = logging.getLogger(__name__)

# Agent 指令模板
LEGAL_AGENT_INSTRUCTIONS = """你是一个专业的法律顾问助手。

你的职责：
1. 回答用户的法律问题，提供准确的法律信息
2. 当需要查询最新信息或不在本地知识库中的内容时，使用 web_search 工具搜索互联网
3. 提醒用户这仅供参考，不是正式法律意见

回答要求：
- 语气专业、友好
- 复杂问题建议咨询专业律师
- 如果需要查询特定法律条文，主动使用 web_search 工具搜索"""


def create_legal_agent(model: Optional[OpenAIChatCompletionsModel] = None) -> Agent:
    """创建法律助手 Agent
    
    Args:
        model: 可选的模型实例，默认使用配置中的模型
    
    Returns:
        配置好的 Agent 实例
    """
    if model is None:
        model = config.get_model()
    
    return Agent(
        name="法律助手",
        instructions=LEGAL_AGENT_INSTRUCTIONS,
        model=model,
        tools=TOOLS,
    )


# 默认 Agent 实例
legal_agent = create_legal_agent()