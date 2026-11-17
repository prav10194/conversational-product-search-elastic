"""Settings, read from environment variables (or a .env file in the project folder)."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
# Elastic's start-local writes its own .env; read it too if it's in this folder.
load_dotenv(ROOT / "elastic-start-local" / ".env", override=False)
# Optional extra env file (keys: ES_URL/ES_API_KEY, or API_endpoint/API_key/Username/Password)
if os.getenv("CREDS_FILE"):
    load_dotenv(os.getenv("CREDS_FILE"), override=False)

ES_URL = os.getenv("ES_URL") or os.getenv("API_endpoint") or os.getenv("ES_LOCAL_URL") or "http://localhost:9200"
ES_API_KEY = os.getenv("ES_API_KEY") or os.getenv("API_key") or os.getenv("ES_LOCAL_API_KEY")
ES_USERNAME = os.getenv("ES_USERNAME") or os.getenv("Username") or "elastic"
ES_PASSWORD = os.getenv("ES_PASSWORD") or os.getenv("Password") or os.getenv("ES_LOCAL_PASSWORD")
ES_CA_CERT = os.getenv("ES_CA_CERT")  # path to ca.crt (used on Kubernetes with ECK)
KIBANA_URL = os.getenv("KIBANA_URL", "http://localhost:5601")

PRODUCTS_INDEX = os.getenv("PRODUCTS_INDEX", "grocery-products")
LOGS_INDEX = os.getenv("LOGS_INDEX", "search-logs")
SEMANTIC_FIELD = "semantic_all"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-5-5")

DEFAULT_STORE = os.getenv("DEFAULT_STORE", "store-1001")
STORES = [f"store-{n}" for n in range(1001, 1011)]
PORT = int(os.getenv("PORT", "8080"))
