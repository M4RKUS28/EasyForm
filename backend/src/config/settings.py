import logging
import os

from typing import Literal, cast
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO)

load_dotenv()

# Password policy defaults
PASSWORD_MIN_LENGTH = 3
PASSWORD_REQUIRE_UPPERCASE = False
PASSWORD_REQUIRE_LOWERCASE = False
PASSWORD_REQUIRE_DIGIT = False
PASSWORD_REQUIRE_SPECIAL_CHAR = False
PASSWORD_SPECIAL_CHARACTERS_REGEX_PATTERN = r'[!@#$%^&*(),.?":{}|<>]'

# JWT settings
ALGORITHM = "HS256"
SECRET_KEY = os.getenv("SECRET_KEY")
SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY")

if not SECRET_KEY or not SESSION_SECRET_KEY:
    raise ValueError("SECRET_KEY and SESSION_SECRET_KEY must be set as environment variables")

######
#ALGORITHM: str = "RS256"
#### Private Key (zum Signieren)
# openssl genrsa -out private.pem 2048
#### Public Key (zum Verifizieren)
# openssl rsa -in private.pem -pubout -out public.pem
PUBLIC_KEY: str = os.getenv("PUBLIC_KEY", "")
PRIVATE_KEY: str =  os.getenv("PRIVATE_KEY", "")
######


ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "150000"))
REFRESH_TOKEN_EXPIRE_MINUTES = int(os.getenv("REFRESH_TOKEN_EXPIRE_MINUTES", "360000")) # 100h
SECURE_COOKIE = os.getenv("SECURE_COOKIE", "true").lower() == "true"



_ALLOWED_SAME_SITE = {"lax", "strict", "none"}
_raw = os.getenv("SAME_SITE", "lax").lower()
if _raw not in _ALLOWED_SAME_SITE:
    raise ValueError(f"Invalid SAME_SITE value: {_raw}")
SAME_SITE = cast(Literal["lax", "strict", "none"], _raw)

# Database Pool settings
DB_POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", "3600"))  
DB_POOL_PRE_PING = os.getenv("DB_POOL_PRE_PING", "true").lower() == "true"
DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "5"))
DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "10"))
DB_CONNECT_TIMEOUT = int(os.getenv("DB_CONNECT_TIMEOUT", "10"))


# Google OAuth settings
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "https://piatto-cooks.com/api/auth/google/callback")
FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "https://piatto-cooks.com/auth/oauth/callback")


AGENT_DEBUG_MODE = os.getenv("AGENT_DEBUG_MODE", "true").lower() == "true"
AGENT_MAX_RETRIES = int(os.getenv("AGENT_MAX_RETRIES", "2"))
AGENT_RETRY_DELAY_SECONDS = float(os.getenv("AGENT_RETRY_DELAY_SECONDS", "2.0"))

# -------------------------
DB_HOST = os.getenv("DB_HOST")  # 10.73.16.3
DB_PORT = os.getenv("DB_PORT", "3306")
DB_USER = os.getenv("DB_USER")  # z. B. root oder custom user
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    DATABASE_URL = f"mysql+aiomysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


PERSONAL_INSTRUCTIONS_MAX_LENGTH = int(os.getenv("PERSONAL_INSTRUCTIONS_MAX_LENGTH", "4000"))

# =============================================
# RAG (Retrieval-Augmented Generation) Settings
# =============================================

# ChromaDB Configuration
CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
CHROMA_AUTH_TOKEN = os.getenv("CHROMA_AUTH_TOKEN", "")

# RAG Processing Configuration
RAG_CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", "1000"))  # tokens per chunk
RAG_CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "200"))  # token overlap
RAG_TOP_K_RESULTS = int(os.getenv("RAG_TOP_K_RESULTS", "10"))  # number of chunks to retrieve

# Tesseract OCR Path
# Windows: Set to Tesseract installation path (e.g., C:\Program Files\Tesseract-OCR\tesseract.exe)
# Docker/Linux: Leave as "tesseract" to use system default
TESSERACT_CMD = os.getenv("TESSERACT_CMD", "tesseract")
