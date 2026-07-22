"""工具函数模块"""
from .web_search import web_search
from .get_current_datetime import get_current_datetime
from .fetch_webpage import fetch_webpage
from .query_legal import query_legal, get_legal_info

# 导出所有工具
TOOLS = [web_search, get_current_datetime, fetch_webpage, query_legal, get_legal_info]

__all__ = ["TOOLS", "web_search", "get_current_datetime", "fetch_webpage", "query_legal", "get_legal_info"]