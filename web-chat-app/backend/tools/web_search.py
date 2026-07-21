"""Web搜索工具"""
import logging

import httpx
from agents import function_tool

from config import config

logger = logging.getLogger(__name__)


@function_tool
def web_search(query: str) -> str:
    """使用 Tavily 搜索互联网获取最新信息
    
    Args:
        query: 搜索查询关键词
    
    Returns:
        格式化后的搜索结果
    """
    logger.info("call web_search")
    
    tavily_key = config.tavily_api_key
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