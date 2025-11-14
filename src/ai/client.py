import os
from functools import lru_cache
from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_core.language_models import BaseChatModel
from langchain_core.embeddings import Embeddings

load_dotenv()

# Modelos configurables
CHAT_MODEL = os.getenv("LANGCHAIN_CHAT_MODEL", "gemini-2.5-flash")
EMBEDDING_MODEL = os.getenv("LANGCHAIN_EMBEDDING_MODEL", "models/text-embedding-004")
TEMPERATURE = float(os.getenv("LANGCHAIN_TEMPERATURE", "0.3"))


@lru_cache(maxsize=1)
def get_chat_model() -> BaseChatModel:
    """Obtiene el modelo de chat con API key de .env"""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY no configurada en .env")
    
    return ChatGoogleGenerativeAI(
        model=CHAT_MODEL,
        temperature=TEMPERATURE,
        google_api_key=api_key,
        convert_system_message_to_human=True  # Para mejor compatibilidad
    )


@lru_cache(maxsize=1)
def get_embeddings() -> Embeddings:
    """Obtiene el modelo de embeddings"""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY no configurada en .env")
    
    return GoogleGenerativeAIEmbeddings(
        model=EMBEDDING_MODEL,
        google_api_key=api_key
    )