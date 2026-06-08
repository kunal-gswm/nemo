"""Configuration loader for the ChatGPT Telegram Bot.

Loads all settings from environment variables (via .env file)
with sensible defaults where applicable.
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()


def _require_env(key: str) -> str:
    """Retrieve a required environment variable or exit with an error.

    Args:
        key: The environment variable name.

    Returns:
        The value of the environment variable.

    Raises:
        SystemExit: If the variable is not set.
    """
    value = os.getenv(key)
    if not value:
        print(f"[FATAL] Missing required environment variable: {key}")
        sys.exit(1)
    return value


# ── Required Settings ──────────────────────────────────────────────
TELEGRAM_BOT_TOKEN: str = _require_env("TELEGRAM_BOT_TOKEN")
OWNER_USER_ID: int = int(_require_env("OWNER_USER_ID"))

# Accept either session token or access token
CHATGPT_SESSION_TOKEN: str = os.getenv("CHATGPT_SESSION_TOKEN") or os.getenv("CHATGPT_ACCESS_TOKEN")
if not CHATGPT_SESSION_TOKEN:
    print("[FATAL] Missing required environment variable: CHATGPT_SESSION_TOKEN or CHATGPT_ACCESS_TOKEN")
    sys.exit(1)

# ── Optional Settings (with defaults) ─────────────────────────────
SESSION_FILE: str = os.getenv("SESSION_FILE", "session_data.json")
RATE_LIMIT_SECONDS: int = int(os.getenv("RATE_LIMIT_SECONDS", "3"))

