"""配置管理模块"""
import os
import json
import logging
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from openai import AsyncOpenAI
from agents import OpenAIChatCompletionsModel

logger = logging.getLogger(__name__)


@dataclass
class Config:
    """应用配置类"""
    deepseek_api_key: str
    cors_origin: str = "http://localhost:3000"
    deepseek_base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-v4-flash"
    request_timeout: int = 30
    max_history_messages: int = 20
    tavily_api_key: Optional[str] = None
    
    # 内部缓存的客户端和模型实例
    _deepseek_client: Optional[AsyncOpenAI] = None
    _model_instance: Optional[OpenAIChatCompletionsModel] = None
    
    def get_deepseek_client(self) -> AsyncOpenAI:
        """获取 DeepSeek 客户端"""
        if self._deepseek_client is None:
            self._deepseek_client = AsyncOpenAI(
                api_key=self.deepseek_api_key,
                base_url=self.deepseek_base_url,
            )
        return self._deepseek_client
    
    def get_model(self, model_name: str = None) -> OpenAIChatCompletionsModel:
        """获取模型实例"""
        name = model_name or self.model
        if self._model_instance is None or name != self.model:
            self._model_instance = OpenAIChatCompletionsModel(
                model=name,
                openai_client=self.get_deepseek_client()
            )
        return self._model_instance


def load_config() -> Config:
    """从环境变量和配置文件加载配置"""
    
    # 基础配置从环境变量加载
    config_data = {
        "deepseek_api_key": os.getenv("DEEPSEEK_API_KEY"),
        "cors_origin": os.getenv("CORS_ORIGIN", "http://localhost:3000"),
        "deepseek_base_url": os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        "model": os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"),
        "request_timeout": int(os.getenv("REQUEST_TIMEOUT", "30")),
        "max_history_messages": int(os.getenv("MAX_HISTORY_MESSAGES", "20"))
    }
    
    # 如果 API key 不在环境变量，尝试从 config.json 加载
    config_path = Path(__file__).parent / "config.json"
    if config_path.exists():
        try:
            with open(config_path, "r") as f:
                file_config = json.load(f)
                # 仅覆盖环境变量中未设置的项
                if not config_data["deepseek_api_key"]:
                    config_data["deepseek_api_key"] = file_config.get("deepseekApiKey")
                config_data["cors_origin"] = file_config.get("corsOrigin", config_data["cors_origin"])
                config_data["deepseek_base_url"] = file_config.get("deepseekBaseUrl", config_data["deepseek_base_url"])
                config_data["model"] = file_config.get("model", config_data["model"])
                config_data["request_timeout"] = file_config.get("requestTimeout", config_data["request_timeout"])
                config_data["max_history_messages"] = file_config.get("maxHistoryMessages", config_data["max_history_messages"])
                # 从配置文件读取 tavily API key
                config_data["tavily_api_key"] = file_config.get("tavilyApiKey")
        except Exception as e:
            logger.error(f"Failed to load config.json: {e}")
    
    if not config_data["deepseek_api_key"]:
        logger.error("DEEPSEEK_API_KEY is not set and config.json is missing or has no API key")
        raise RuntimeError("DEEPSEEK_API_KEY is not configured")
    
    return Config(**config_data)


# 全局配置实例
config = load_config()