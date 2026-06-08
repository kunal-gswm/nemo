"""Configuration loader for the ChatGPT Telegram Bot.

Loads all settings from environment variables (via .env file)
with sensible defaults where applicable.
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()


import time

def _require_env(key: str) -> str:
    """Retrieve a required environment variable or exit with an error."""
    value = os.getenv(key)
    if not value:
        print(f"[FATAL] Missing required environment variable: {key}", flush=True)
        time.sleep(10) # Sleep so Render has time to show the log
        sys.exit(1)
    return value


# ── Required Settings ──────────────────────────────────────────────
TELEGRAM_BOT_TOKEN: str = _require_env("TELEGRAM_BOT_TOKEN")
OWNER_USER_ID: int = int(_require_env("OWNER_USER_ID"))

# Accept either session token or access token
CHATGPT_SESSION_TOKEN: str = os.getenv("CHATGPT_SESSION_TOKEN") or os.getenv("CHATGPT_ACCESS_TOKEN")
if not CHATGPT_SESSION_TOKEN:
    print("[FATAL] Missing required environment variable: CHATGPT_SESSION_TOKEN or CHATGPT_ACCESS_TOKEN", flush=True)
    time.sleep(10)
    sys.exit(1)

# ── Optional Settings (with defaults) ─────────────────────────────
SESSION_FILE: str = os.getenv("SESSION_FILE", "session_data.json")
RATE_LIMIT_SECONDS: int = int(os.getenv("RATE_LIMIT_SECONDS", "3"))

