import os
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if not os.environ.get("SEHATWARGA_TESTING") and not os.environ.get("PYTHON_DOTENV_DISABLED"):
    load_dotenv(PROJECT_ROOT / ".env")


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-fallback-secret-key-sehatwarga")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "mysql+pymysql://username:password@localhost/sehatwarga"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", 5 * 1024 * 1024))  # 5 MB
    GOOGLE_PLACES_BROWSER_KEY = os.environ.get("GOOGLE_PLACES_BROWSER_KEY", "")
    MAPBOX_PUBLIC_TOKEN = os.environ.get("MAPBOX_PUBLIC_TOKEN", "")
    AI_PROVIDER = os.environ.get("AI_PROVIDER", "fallback")
    AI_API_KEY = os.environ.get("AI_API_KEY", "")
    AI_MODEL = os.environ.get("AI_MODEL", "")
    AI_TIMEOUT_MS = max(10000, min(int(os.environ.get("AI_TIMEOUT_MS", "15000")), 30000))

    OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "")
    OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "")
    OLLAMA_TIMEOUT_SECONDS = os.environ.get(
    "OLLAMA_TIMEOUT_SECONDS", "35"
    )


class TestingConfig(Config):
    MAPBOX_PUBLIC_TOKEN = ""
    TESTING = True
    SECRET_KEY = "testing-only-not-for-deployment"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = True
    AI_PROVIDER = "fallback"
    AI_API_KEY = ""
    AI_MODEL = ""
