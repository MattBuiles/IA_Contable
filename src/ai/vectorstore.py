from pathlib import Path
from typing import List, Tuple

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.retrievers import BaseRetriever
from langchain_community.vectorstores import FAISS

VS_PATH = Path("data/faiss_index")

# Variable global para cachear el vectorstore
_vectorstore_cache = None


def _get_vectorstore(embedder: Embeddings) -> FAISS:
    """
    Obtiene o crea el índice FAISS.
    Usa caché para evitar recargar en cada llamada.
    """
    global _vectorstore_cache
    
    if _vectorstore_cache is not None:
        return _vectorstore_cache
    
    VS_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    # Si existe índice guardado, cargarlo
    if (VS_PATH / "index.faiss").exists():
        _vectorstore_cache = FAISS.load_local(
            str(VS_PATH), 
            embedder, 
            allow_dangerous_deserialization=True
        )
    else:
        # Inicializar con documento dummy
        dummy_docs = [
            Document(
                page_content="Índice vacío. Carga documentos para comenzar.",
                metadata={"type": "placeholder"}
            )
        ]
        _vectorstore_cache = FAISS.from_documents(dummy_docs, embedder)
        _vectorstore_cache.save_local(str(VS_PATH))
    
    return _vectorstore_cache


def get_retriever(embedder: Embeddings, k: int = 4) -> BaseRetriever:
    """
    Retorna un retriever FAISS optimizado.
    
    Args:
        embedder: Modelo de embeddings
        k: Número de documentos a recuperar
    
    Returns:
        Retriever FAISS
    """
    vectorstore = _get_vectorstore(embedder)
    return vectorstore.as_retriever(
        search_type="similarity",
        search_kwargs={"k": k}
    )


def index_documents(docs: List[Document], embedder: Embeddings) -> None:
    """
    Indexa documentos en FAISS.
    
    Args:
        docs: Lista de documentos a indexar
        embedder: Modelo de embeddings
    """
    global _vectorstore_cache
    
    if not docs:
        return
    
    vectorstore = _get_vectorstore(embedder)
    vectorstore.add_documents(docs)
    vectorstore.save_local(str(VS_PATH))


def clear_vectorstore() -> None:
    """Limpia el cache del vectorstore"""
    global _vectorstore_cache
    _vectorstore_cache = None