"""法律条文查询工具"""
import json
import logging
from pathlib import Path
from typing import Optional

from agents import function_tool

logger = logging.getLogger(__name__)

# 法律文档目录
LEGAL_DIR = Path(__file__).parent.parent / "legal_konwlegde"
INDEX_FILE = LEGAL_DIR / "legal_docs_index.json"

# 缓存法律数据
_legal_cache = {}
_index_cache = None


def _load_index() -> dict:
    """加载法律索引文件"""
    global _index_cache
    if _index_cache is None:
        with open(INDEX_FILE, 'r', encoding='utf-8') as f:
            _index_cache = json.load(f)
    return _index_cache


def _load_legal_file(filename: str) -> dict:
    """加载法律文件（带缓存）"""
    if filename not in _legal_cache:
        filepath = LEGAL_DIR / filename
        with open(filepath, 'r', encoding='utf-8') as f:
            _legal_cache[filename] = json.load(f)
    return _legal_cache[filename]


def _normalize_article_number(article_num: str) -> str:
    """标准化条款编号"""
    # 去除"第"、"条"等，转换为数字
    num = article_num.replace("第", "").replace("条", "").strip()
    
    # 中文数字转阿拉伯数字
    cn_num_map = {
        "一": "1", "二": "2", "三": "3", "四": "4", "五": "5",
        "六": "6", "七": "7", "八": "8", "九": "9", "十": "10",
        "十一": "11", "十二": "12", "十三": "13", "十四": "14", "十五": "15",
        "十六": "16", "十七": "17", "十八": "18", "十九": "19", "二十": "20"
    }
    
    if num in cn_num_map:
        num = cn_num_map[num]
    
    return f"第{num}条"


def _find_article_by_number(clauses: list, article_num: str) -> Optional[dict]:
    """根据条款编号查找法条"""
    # 尝试多种格式匹配
    normalized = _normalize_article_number(article_num)
    
    # 直接匹配
    for clause in clauses:
        if clause.get("编号") == article_num:
            return clause
    
    # 标准化匹配
    for clause in clauses:
        if clause.get("编号") == normalized:
            return clause
    
    # 模糊匹配（包含数字）
    for clause in clauses:
        clause_num = clause.get("编号", "")
        # 提取数字部分
        import re
        nums = re.findall(r'\d+', clause_num)
        target_nums = re.findall(r'\d+', normalized)
        if nums and target_nums and nums[0] == target_nums[0]:
            return clause
    
    return None


def _search_by_keyword(clauses: list, keyword: str, limit: int = 5) -> list:
    """根据关键词搜索条款"""
    results = []
    keyword = keyword.lower()
    
    for clause in clauses:
        content = clause.get("内容", "").lower()
        clause_num = clause.get("编号", "")
        tags = clause.get("标签", [])
        
        # 检查内容、编号、标签是否包含关键词
        if keyword in content or keyword in clause_num or any(keyword in tag.lower() for tag in tags):
            results.append({
                "编号": clause_num,
                "内容": clause.get("内容", "")[:200] + "..." if len(clause.get("内容", "")) > 200 else clause.get("内容", ""),
                "id": clause.get("id"),
                "标签": tags
            })
        
        if len(results) >= limit:
            break
    
    return results


def _search_by_tag(clauses: list, tag: str, limit: int = 5) -> list:
    """根据标签搜索条款"""
    results = []
    tag = tag.lower()
    
    for clause in clauses:
        tags = clause.get("标签", [])
        if any(tag in t.lower() for t in tags):
            results.append({
                "编号": clause.get("编号"),
                "内容": clause.get("内容", "")[:200] + "..." if len(clause.get("内容", "")) > 200 else clause.get("内容", ""),
                "id": clause.get("id"),
                "标签": tags
            })
        
        if len(results) >= limit:
            break
    
    return results


@function_tool
def query_legal(
    article_number: Optional[str] = None,
    keyword: Optional[str] = None,
    tag: Optional[str] = None,
    law: Optional[str] = None
) -> str:
    """查询法律条款信息
    
    根据条款编号、关键词或标签查询法律条文。
    必须提供至少一个查询条件：article_number、keyword 或 tag。
    
    Args:
        article_number: 条款编号，如 "第26条" 或 "第二十六条"
        keyword: 关键词，如 "监护人"、"合同"、"侵权"
        tag: 标签，如 "婚姻家庭"、"侵权责任"
        law: 法律文件名，如 "minfadian.json"，不填则默认搜索民法典
    
    Returns:
        查询结果，包含条款编号、内容、ID和标签
    
    Examples:
        - query_legal(article_number="第二十六条")  # 查询第26条
        - query_legal(keyword="监护人")  # 搜索包含"监护人"的条款
        - query_legal(tag="婚姻家庭")  # 搜索标签为"婚姻家庭"的条款
    """
    logger.info(f"query_legal: article={article_number}, keyword={keyword}, tag={tag}, law={law}")
    
    # 加载索引
    index = _load_index()
    
    # 确定要查询的法律文件
    if law:
        # 用户指定了法律
        law_file = law
    else:
        # 使用默认法律
        law_file = index.get("全局配置", {}).get("默认法律", "minfadian.json")
    
    # 验证法律文件存在
    law_list = index.get("文档列表", [])
    law_info = None
    for l in law_list:
        if l.get("文件名") == law_file:
            law_info = l
            break
    
    if not law_info:
        return f"错误：未找到法律文件 '{law}'。可用法律：{', '.join([l['文件名'] for l in law_list])}"
    
    # 加载法律内容
    try:
        legal_data = _load_legal_file(law_file)
    except FileNotFoundError:
        return f"错误：法律文件 '{law_file}' 不存在"
    
    clauses = legal_data.get("条款", [])
    
    # 执行查询
    results = []
    
    if article_number:
        # 按条款编号查询
        article = _find_article_by_number(clauses, article_number)
        if article:
            results = [{
                "编号": article.get("编号"),
                "内容": article.get("内容"),
                "id": article.get("id"),
                "标签": article.get("标签", [])
            }]
        else:
            return f"未找到条款 '{article_number}'"
    
    elif keyword:
        # 按关键词搜索
        results = _search_by_keyword(clauses, keyword)
        if not results:
            return f"未找到包含关键词 '{keyword}' 的条款"
    
    elif tag:
        # 按标签搜索
        results = _search_by_tag(clauses, tag)
        if not results:
            return f"未找到标签为 '{tag}' 的条款"
    
    else:
        return "错误：必须提供 article_number、keyword 或 tag 之一作为查询条件"
    
    # 格式化输出
    law_name = law_info.get("法律名称", law_file)
    
    output = [f"【{law_name}】查询结果：", ""]
    
    for i, r in enumerate(results, 1):
        output.append(f"第{i}条：{r['编号']}")
        output.append(f"ID: {r['id']}")
        output.append(f"内容：{r['内容']}")
        if r.get("标签"):
            output.append(f"标签：{', '.join(r['标签'])}")
        output.append("")
    
    if len(results) > 1:
        output.append(f"共找到 {len(results)} 条相关条款")
    
    return "\n".join(output)


@function_tool
def get_legal_info(law: Optional[str] = None) -> str:
    """获取法律文件的基本信息
    
    Args:
        law: 法律文件名，如 "minfadian.json"，不填则返回所有法律列表
    
    Returns:
        法律的基本信息
    """
    logger.info(f"get_legal_info: law={law}")
    
    index = _load_index()
    law_list = index.get("文档列表", [])
    
    if law:
        # 返回指定法律信息
        for l in law_list:
            if l.get("文件名") == law:
                info = [
                    f"【{l.get('法律名称')}】",
                    f"简称：{l.get('简称', '无')}",
                    f"英文名：{l.get('英文名', '无')}",
                    f"颁布时间：{l.get('颁布时间')}",
                    f"条款数：{l.get('条款数')} 条",
                    f"标签：{', '.join(l.get('标签', []))}",
                    f"主题分类：{', '.join(l.get('主题分类', []))}",
                    f"关键词：{', '.join(l.get('关键词', []))}",
                    f"适用场景：{', '.join(l.get('适用场景', []))}",
                    f"简介：{l.get('简介', '无')}",
                ]
                return "\n".join(info)
        return f"未找到法律文件 '{law}'"
    else:
        # 返回所有法律列表
        output = ["【法律文档索引】", ""]
        for l in law_list:
            output.append(f"- {l.get('法律名称')} ({l.get('简称')})")
            output.append(f"  文件名：{l.get('文件名')}")
            output.append(f"  条款数：{l.get('条款数')} 条")
            output.append(f"  标签：{', '.join(l.get('标签', []))}")
            output.append("")
        
        output.append("使用方法：")
        output.append("- query_legal(article_number='第26条')  # 按条款编号查询")
        output.append("- query_legal(keyword='监护人')  # 按关键词搜索")
        output.append("- query_legal(tag='婚姻家庭')  # 按标签搜索")
        output.append("- get_legal_info(law='minfadian.json')  # 获取法律信息")
        
        return "\n".join(output)