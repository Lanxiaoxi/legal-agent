"""网页抓取工具"""
import logging
import random
import time

import httpx
from bs4 import BeautifulSoup
from agents import function_tool

logger = logging.getLogger(__name__)

# User-Agent 轮换池 - 多个真实浏览器标识
USER_AGENT_POOL = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
]

# 请求头轮换池
HEADERS_POOL = [
    {
        'User-Agent': random.choice(USER_AGENT_POOL),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Cache-Control': 'max-age=0',
    },
    {
        'User-Agent': random.choice(USER_AGENT_POOL),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    },
]


def get_random_headers() -> dict:
    """从池中随机获取请求头"""
    return random.choice(HEADERS_POOL)


@function_tool
def fetch_webpage(url: str) -> str:
    """抓取网页内容
    
    Args:
        url: 目标网页 URL
    
    Returns:
        提取的网页文本内容
    """
    start_time = time.time()
    logger.info(f"[TOOL_CALL] fetch_webpage - url: {url}")
    
    # 从池中随机获取请求头
    headers = get_random_headers()
    
    try:
        response = httpx.get(url, headers=headers, timeout=10.0, follow_redirects=True)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 去除脚本和样式
        for script in soup(['script', 'style']):
            script.decompose()
        
        text = soup.get_text(separator='\n', strip=True)
        
        # 清理空行
        lines = [line for line in text.split('\n') if line.strip()]
        text = '\n'.join(lines)
        
        # 限制返回长度
        if len(text) > 5000:
            text = text[:5000] + "\n\n[内容已被截断...]"
        
        elapsed_ms = (time.time() - start_time) * 1000
        logger.info(f"[TOOL_END] fetch_webpage completed - url: {url}, content_length: {len(text)}, elapsed: {elapsed_ms:.0f}ms")
        return f"网页内容 ({url}):\n\n{text}"
        
    except httpx.TimeoutException:
        elapsed_ms = (time.time() - start_time) * 1000
        logger.warning(f"[TOOL_ERROR] fetch_webpage timeout - url: {url}, elapsed: {elapsed_ms:.0f}ms")
        return "抓取失败: 请求超时"
    except httpx.HTTPStatusError as e:
        elapsed_ms = (time.time() - start_time) * 1000
        logger.warning(f"[TOOL_ERROR] fetch_webpage HTTP error - url: {url}, status: {e.response.status_code}, elapsed: {elapsed_ms:.0f}ms")
        return f"抓取失败: HTTP {e.response.status_code}"
    except Exception as e:
        elapsed_ms = (time.time() - start_time) * 1000
        logger.error(f"[TOOL_ERROR] fetch_webpage failed - url: {url}, error: {e}, elapsed: {elapsed_ms:.0f}ms")
        return f"抓取失败: {str(e)}"