import os

APP_NAME = os.getenv("APP_NAME", "DEVORA AI")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "qwen2.5:7b")
DATABASE_PATH = os.getenv("DATABASE_PATH", "./data/devora.db")
