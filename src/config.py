"""
Configuración centralizada para la aplicación IA Contable.
Sigue las mejores prácticas de LangChain 1.0.5+
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ===== Paths =====
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "contabilidad.db"
FAISS_PATH = DATA_DIR / "faiss_index"

# ===== LLM Configuration =====
CHAT_MODEL = os.getenv("LANGCHAIN_CHAT_MODEL", "gemini-2.5-flash")
EMBEDDING_MODEL = os.getenv("LANGCHAIN_EMBEDDING_MODEL", "models/text-embedding-004")
TEMPERATURE = float(os.getenv("LANGCHAIN_TEMPERATURE", "0.3"))
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY no configurada en .env")

# ===== RAG Configuration =====
RETRIEVER_K = int(os.getenv("RETRIEVER_K", "4"))
MAX_SQL_RESULTS = int(os.getenv("MAX_SQL_RESULTS", "50"))

# ===== Database Configuration =====
DEFAULT_CURRENCY = os.getenv("DEFAULT_CURRENCY", "COP")
TAX_RATE = float(os.getenv("TAX_RATE", "0.19"))

# ===== Logging =====
DEBUG_MODE = os.getenv("DEBUG_MODE", "False").lower() == "true"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
