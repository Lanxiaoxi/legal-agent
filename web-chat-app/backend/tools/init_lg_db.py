# scripts/init_legal_kb.py
import os
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from pinecone_search import PineconeVectorSearch
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_sample_legal_documents():
    """从 doc 目录读取法律文档"""
    # 从 tools 目录向上两级到 web-chat-app，再向上到项目根目录
    doc_dir = Path(__file__).parent.parent.parent.parent / "doc"
    
    # 绝对路径调试
    print(f"DEBUG: __file__ = {__file__}")
    print(f"DEBUG: doc_dir = {doc_dir}")
    print(f"DEBUG: doc_dir exists = {doc_dir.exists()}")
    
    documents = []
    
    # 读取 minfadian.txt (民法典)
    minfadian_path = doc_dir / "minfadian.txt"
    if minfadian_path.exists():
        documents.append({
            "source": "民法典",
            "category": "民法",
            "content": minfadian_path.read_text(encoding="utf-8")
        })
    
    # 读取 xingfa.txt (刑法)
    xingfa_path = doc_dir / "xingfa.txt"
    if xingfa_path.exists():
        documents.append({
            "source": "刑法",
            "category": "刑法",
            "content": xingfa_path.read_text(encoding="utf-8")
        })
    
    # 读取 xianfa.txt (宪法)
    xianfa_path = doc_dir / "xianfa.txt"
    if xianfa_path.exists():
        documents.append({
            "source": "宪法",
            "category": "宪法",
            "content": xianfa_path.read_text(encoding="utf-8")
        })
    
    return documents

def initialize_knowledge_base():
    """初始化法律知识库"""
    logger.info("🚀 开始初始化法律知识库...")
    
    try:
        # 初始化Pinecone
        vector_search = PineconeVectorSearch()
        vector_search.ensure_index_exists()
        
        # 获取示例文档
        # documents = get_sample_legal_documents()
        # logger.info(f"📚 准备添加 {len(documents)} 个法律文档")
        
        # 添加文档到Pinecone
        # vector_search.add_documents(documents)
        
        logger.info("✅ 法律知识库初始化完成！")
        logger.info("📌 你现在可以使用Agent进行法律问询了")
        
        # 测试搜索
        test_query = "故意伤人是怎么判的"
        logger.info(f"\n🔍 测试搜索: '{test_query}'")
        results = vector_search.search(test_query, top_k=3)
        
        logger.info(f"📋 搜索结果:")
        for i, result in enumerate(results, 1):
            logger.info(f"\n{i}. [相似度: {result['score']:.3f}] 来源: {result['source']}")
            logger.info(f"   内容预览: {result['content'][:100]}...")
        
    except Exception as e:
        logger.error(f"❌ 初始化失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    initialize_knowledge_base()