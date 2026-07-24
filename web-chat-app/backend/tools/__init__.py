"""工具函数模块"""
from .web_search import web_search
from .get_current_datetime import get_current_datetime
from .fetch_webpage import fetch_webpage
from .query_legal import query_legal, get_legal_info
from .search_uploaded_file import search_uploaded_file

# 所有工具
TOOLS = [web_search, get_current_datetime, fetch_webpage, query_legal, get_legal_info, search_uploaded_file]

# 不含 web_search 的工具列表
TOOLS_WITHOUT_WEB_SEARCH = [t for t in TOOLS if t is not web_search]


def get_tools(enable_web_search: bool = True) -> list:
    """根据是否启用联网搜索返回对应的工具列表"""
    return TOOLS if enable_web_search else TOOLS_WITHOUT_WEB_SEARCH


__all__ = ["TOOLS", "TOOLS_WITHOUT_WEB_SEARCH", "get_tools",
           "web_search", "get_current_datetime", "fetch_webpage",
           "query_legal", "get_legal_info", "search_uploaded_file"]