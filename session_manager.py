"""Session token persistence and refresh logic.

Stores the ChatGPT session token in a local JSON file so that
refreshed tokens survive restarts. On startup the saved token
is preferred over the .env value because it is more recent.
"""

import json
import logging
from pathlib import Path
from typing import Optional

import aiofiles

import config

logger = logging.getLogger(__name__)


async def load_token() -> str:
    """Load the most recent session token.

    Precedence:
        1. Token stored in the session file (freshest).
        2. Token from the .env / environment variable (fallback).

    Returns:
        The session token string.
    """
    session_path = Path(config.SESSION_FILE)

    if session_path.exists():
        try:
            async with aiofiles.open(session_path, mode="r", encoding="utf-8") as fh:
                data: dict = json.loads(await fh.read())
            token: Optional[str] = data.get("session_token")
            if token:
                logger.info("Loaded session token from %s", config.SESSION_FILE)
                return token
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning(
                "Failed to read %s (%s); falling back to env token.",
                config.SESSION_FILE,
                exc,
            )

    logger.info("Using session token from environment variable.")
    return config.CHATGPT_SESSION_TOKEN


async def save_token(token: str) -> None:
    """Persist a session token to the JSON file.

    Args:
        token: The new session token value.
    """
    payload = json.dumps({"session_token": token}, indent=2)
    async with aiofiles.open(config.SESSION_FILE, mode="w", encoding="utf-8") as fh:
        await fh.write(payload)
    logger.info("Session token saved to %s", config.SESSION_FILE)


def token_exists() -> bool:
    """Check whether a persisted session file exists on disk.

    Returns:
        True if the session file is present.
    """
    exists = Path(config.SESSION_FILE).exists()
    logger.debug("token_exists() -> %s", exists)
    return exists
