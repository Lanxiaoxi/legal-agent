# tools/pinecone_search.py
import os
import logging
from pathlib import Path
from typing import List, Dict

# 设置 HuggingFace 镜像和缓存目录（解决国内网络问题）
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

# 指定本地模型缓存目录（tools 目录下的 .cache 文件夹）
MODEL_CACHE_DIR = Path(__file__).parent / ".cache"
os.environ.setdefault("HF_HOME", str(MODEL_CACHE_DIR))
os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", str(MODEL_CACHE_DIR))

from pinecone import Pinecone, ServerlessSpec
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

class PineconeVectorSearch:
    _model_cache = None  # 类变量缓存模型

    def __init__(self, use_local_embedding: bool = True):
        """初始化 Pinecone 连接和本地 Embedding 模型

        Args:
            use_local_embedding: 是否使用本地 Embedding 模型（默认 True）
        """
        # Pinecone 配置
        api_key = os.getenv("PINECONE_API_KEY")
        if not api_key:
            raise ValueError("PINECONE_API_KEY 未设置")

        self.pc = Pinecone(api_key=api_key)
        self.index_name = "legal-knowledge"
        self.index = self.pc.Index(self.index_name)

        # 本地 Embedding 模型（使用缓存避免重复下载）
        self.use_local_embedding = use_local_embedding

        if use_local_embedding:
            if PineconeVectorSearch._model_cache is None:
                logger.info("首次加载本地 Embedding 模型...")
                model_name = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
                
                # 强制只从本地加载，不检查远程更新
                PineconeVectorSearch._model_cache = SentenceTransformer(
                    model_name,
                    cache_folder=str(MODEL_CACHE_DIR),
                    local_files_only=True  # 强制从本地缓存加载
                )
                
                logger.info(f"✓ 模型已加载到内存，缓存目录: {MODEL_CACHE_DIR}")
            else:
                logger.info("✓ 使用已缓存模型（无需重新下载）")
            self.embedding_model = PineconeVectorSearch._model_cache

    def ensure_index_exists(self):
        """确保索引存在"""
        try:
            self.index.describe_index_stats()
            logger.info(f"✅ 索引 '{self.index_name}' 已存在")
        except Exception as e:
            logger.info(f"📝 创建新索引 '{self.index_name}'")
            self.pc.create_index(
                name=self.index_name,
                dimension=384,  # MiniLM 模型输出维度为 384
                metric="cosine",
                spec=ServerlessSpec(
                    cloud="aws",
                    region="us-west-2"
                )
            )

    def add_documents(self, documents: List[Dict[str, str]], batch_size: int = 100):
        """添加法律文档到 Pinecone

        Args:
            documents: 文档列表
            batch_size: 批量上传大小
        """
        vectors_to_upsert = []

        for doc_idx, doc in enumerate(documents):
            content = doc.get("content", "")
            source = doc.get("source", "unknown")
            category = doc.get("category", "general")

            # 分块处理长文档
            chunks = self._chunk_text(content, chunk_size=800, overlap=200)

            for chunk_idx, chunk in enumerate(chunks):
                try:
                    # 生成向量
                    embedding = self._get_embedding(chunk)

                    # 准备上传数据
                    vector_id = f"doc-{doc_idx}-chunk-{chunk_idx}"
                    vectors_to_upsert.append((
                        vector_id,
                        embedding,
                        {
                            "text": chunk,
                            "source": source,
                            "category": category,
                            "full_doc_id": str(doc_idx),
                            "chunk_id": str(chunk_idx)
                        }
                    ))
                except Exception as e:
                    logger.error(f"处理文档 {doc_idx} 块 {chunk_idx} 失败: {e}")
                    continue

        # 批量上传
        self._batch_upsert(vectors_to_upsert, batch_size)
        logger.info(f"✅ 已上传 {len(vectors_to_upsert)} 个向量")

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, any]]:
        """向量搜索

        Args:
            query: 查询文本
            top_k: 返回结果数量

        Returns:
            搜索结果列表
        """
        try:
            # 将查询转换为向量
            query_embedding = self._get_embedding(query)

            # 从 Pinecone 搜索
            results = self.index.query(
                vector=query_embedding,
                top_k=top_k,
                include_metadata=True
            )

            # 格式化结果
            formatted_results = []
            for match in results.matches:
                formatted_results.append({
                    "content": match.metadata.get("text", ""),
                    "source": match.metadata.get("source", ""),
                    "category": match.metadata.get("category", ""),
                    "score": float(match.score),
                    "id": match.id
                })

            logger.info(f"✅ 搜索完成，返回 {len(formatted_results)} 个结果")
            return formatted_results

        except Exception as e:
            logger.error(f"搜索失败: {e}")
            return []

    # ========== 私有方法 ==========

    def _get_embedding(self, text: str) -> List[float]:
        """生成 Embedding - 直接使用缓存模型"""
        # 模型已在内存中，直接调用
        embedding = self.embedding_model.encode(
            text,
            convert_to_tensor=False,
            normalize_embeddings=True
        )
        logger.debug(f"生成 Embedding 维度: {len(embedding)}")
        return embedding.tolist()

    def _chunk_text(self, text: str, chunk_size: int = 800, overlap: int = 200) -> List[str]:
        """分块处理文本"""
        chunks = []
        step = chunk_size - overlap
        for i in range(0, len(text), step):
            chunk = text[i:i + chunk_size]
            if chunk.strip():
                chunks.append(chunk)
        return chunks if chunks else [text]

    def _batch_upsert(self, vectors: List, batch_size: int = 100):
        """批量上传向量"""
        for i in range(0, len(vectors), batch_size):
            batch = vectors[i:i + batch_size]
            try:
                self.index.upsert(vectors=batch)
                logger.info(f"✅ 已上传批次 {i // batch_size + 1}")
            except Exception as e:
                logger.error(f"上传批次失败: {e}")

    def delete_index(self):
        """删除索引（仅用于测试）"""
        try:
            self.pc.delete_index(self.index_name)
            logger.info(f"✅ 索引 '{self.index_name}' 已删除")
        except Exception as e:
            logger.error(f"删除索引失败: {e}")