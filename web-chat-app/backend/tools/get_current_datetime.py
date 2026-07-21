"""获取当前日期时间工具"""
import logging
from datetime import datetime
from agents import function_tool

logger = logging.getLogger(__name__)


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