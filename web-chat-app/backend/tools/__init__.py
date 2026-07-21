"""工具函数模块"""
from .web_search import web_search
from .get_current_datetime import get_current_datetime
from .fetch_webpage import fetch_webpage

# 导出所有工具
TOOLS = [web_search, get_current_datetime, fetch_webpage]

__all__ = ["TOOLS", "web_search", "get_current_datetime", "fetch_webpage"]