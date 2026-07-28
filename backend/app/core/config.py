"""ProductIQ configuration — loads .env, exposes settings."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BASE_DIR.parent
DATA_DIR = PROJECT_ROOT / "datasets"
SQLITE_DIR = PROJECT_ROOT / "data"

load_dotenv(BASE_DIR / ".env")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
TAVILY_MCP_COMMAND = os.getenv("TAVILY_MCP_COMMAND", "npx")
TAVILY_MCP_ARGS = os.getenv("TAVILY_MCP_ARGS", "-y tavily-mcp")
RESEARCH_CACHE_TTL_HOURS = float(os.getenv("RESEARCH_CACHE_TTL_HOURS", "6"))
RESEARCH_MONTHLY_BUDGET = int(os.getenv("RESEARCH_MONTHLY_BUDGET", "900"))
RESEARCH_TIMEOUT_SECONDS = float(os.getenv("RESEARCH_TIMEOUT_SECONDS", "20"))
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
COOKIE_SECRET = os.getenv("COOKIE_SECRET", "change-this-secret-in-production")
API_HOST = "127.0.0.1"
API_PORT = 8000
