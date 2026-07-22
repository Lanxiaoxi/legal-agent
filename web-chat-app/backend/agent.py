"""Agent 定义模块"""
import logging
from typing import Optional

from agents import Agent, OpenAIChatCompletionsModel

from config import config
from tools import TOOLS

logger = logging.getLogger(__name__)

# Agent 指令模板
LEGAL_AGENT_INSTRUCTIONS = """你是一个专业的法律顾问助手。

## 你的职责
1. 回答用户的法律问题，提供准确的法律信息
2. 提醒用户这仅供参考，复杂问题建议咨询专业律师

## 工具使用指南

### 本地法律数据库（优先使用）
当你需要查询中国法律条文时，使用 `query_legal` 工具：
获取法律列表：`get_legal_info()`

### 互联网搜索
当问题涉及以下情况时，使用 `web_search` 工具搜索互联网：
- 需要最新法律法规或司法解释
- 本地知识库中没有的内容
- 查找具体案例

### 网页抓取
当需要获取特定网页的详细内容时，使用 `fetch_webpage` 工具。

### 时间查询
当问题涉及时间期限、时效计算时，使用 `get_current_datetime` 工具。

## 回答要求
- 语气专业、友好
- 优先使用本地法律数据库回答
- 如果引用法条，注明来源
- 如果引用链接，附在回答最后
- 遇到不确定的问题，坦诚告知并建议咨询专业律师"""


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