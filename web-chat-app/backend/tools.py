"""工具函数模块"""
import logging
from datetime import datetime
from typing import Optional

from agents import function_tool
import httpx

from config import config

logger = logging.getLogger(__name__)


@function_tool
def get_legal_reference(law_type: str) -> str:
    """获取法律条文参考
    
    Args:
        law_type: 法律类型，可选值: contract(合同法), property(物权法), 
                  civil(民法典), labor(劳动法), criminal(刑法)
    
    Returns:
        相关法律条文内容
    """
    logger.info("call get_legal_reference")
    
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
    """根据关键词搜索相关法律条文
    
    Args:
        keyword: 要搜索的法律关键词，如：违约金、侵权、租赁等
    
    Returns:
        相关法律条文内容
    """
    logger.info("call search_legal_keyword")
    
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


@function_tool
def get_current_datetime() -> str:
    """获取当前的日期和时间
    
    Returns:
        当前日期时间，格式为 "YYYY年MM月DD日 HH:mm:ss 星期X"
    """
    logger.info("call get_current_datetime")
    
    now = datetime.now()
    
    # 格式化日期时间
    date_str = now.strftime("%Y年%m月%d日")
    time_str = now.strftime("%H:%M:%S")
    
    # 星期
    weekday_names = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    weekday = weekday_names[now.weekday()]

    return f"当前时间是：{date_str} {time_str} {weekday}"


# 导出所有工具
TOOLS = [get_legal_reference, search_legal_keyword, web_search, get_current_datetime]