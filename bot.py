"""Main Telegram bot for ChatGPT integration.

Routes user messages to ChatGPT via a browser session token,
manages per-user conversations, and provides admin commands
for token management.
"""

from __future__ import annotations

import asyncio
import logging
import platform
import signal
import sys
import os
import time
from typing import Dict, Optional

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from aiohttp import web

import config
from chatgpt_client import ChatGPTClient, ChatGPTError, SessionExpiredError
from session_manager import load_token, save_token, token_exists

# ── Logging ────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# ── State ──────────────────────────────────────────────────────────

# Per-user conversation tracking: {user_id: conversation_id}
user_conversations: Dict[int, str] = {}

# Per-user rate limiting: {user_id: last_message_epoch}
user_last_message: Dict[int, float] = {}

# Initialised in main() after loading the token
chatgpt_client: ChatGPTClient | None = None


# ── Helpers ────────────────────────────────────────────────────────

def _is_rate_limited(user_id: int) -> bool:
    """Check whether a user is sending messages too quickly.

    Args:
        user_id: Telegram user ID.

    Returns:
        True if the user should be throttled.
    """
    now = time.time()
    last = user_last_message.get(user_id, 0.0)
    if now - last < config.RATE_LIMIT_SECONDS:
        return True
    user_last_message[user_id] = now
    return False


def _is_owner(user_id: int) -> bool:
    """Return True if *user_id* matches the configured bot owner."""
    return user_id == config.OWNER_USER_ID


# ── Command Handlers ──────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /start command with a welcome message.

    Args:
        update: Incoming Telegram update.
        context: Bot context.
    """
    welcome = (
        "👋 *Welcome to the ChatGPT Bot!*\n\n"
        "Just send me any message and I'll forward it to ChatGPT.\n\n"
        "*Available commands:*\n"
        "/reset — Start a fresh conversation\n"
        "/status — Show bot & session status\n"
        "/settoken `<token>` — _(owner only)_ Update the session token\n"
    )
    await update.message.reply_text(welcome, parse_mode="Markdown")
    logger.info("/start from user %s", update.effective_user.id)


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /reset command — clears the user's conversation history.

    Args:
        update: Incoming Telegram update.
        context: Bot context.
    """
    user_id = update.effective_user.id
    old = user_conversations.pop(user_id, None)
    await update.message.reply_text("🔄 Conversation reset. Send a new message to begin.")
    logger.info("/reset from user %s (old conversation=%s)", user_id, old)


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /status command — reports bot health.

    Args:
        update: Incoming Telegram update.
        context: Bot context.
    """
    session_loaded = chatgpt_client is not None
    persisted = token_exists()
    user_id = update.effective_user.id
    active_convo = user_conversations.get(user_id, "none")

    status_text = (
        "📊 *Bot Status*\n\n"
        f"• Session token loaded: `{'✅ Yes' if session_loaded else '❌ No'}`\n"
        f"• Persisted token file: `{'✅ Found' if persisted else '❌ Not found'}`\n"
        f"• Your conversation: `{active_convo}`\n"
        f"• Rate limit: `{config.RATE_LIMIT_SECONDS}s`\n"
    )
    await update.message.reply_text(status_text, parse_mode="Markdown")
    logger.info("/status from user %s", user_id)


async def cmd_settoken(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the /settoken command — hot-swaps the session token (owner only).

    Usage: ``/settoken <new_session_token>``

    Args:
        update: Incoming Telegram update.
        context: Bot context.
    """
    global chatgpt_client

    user_id = update.effective_user.id
    if not _is_owner(user_id):
        await update.message.reply_text("🚫 Only the bot owner can update the token.")
        logger.warning("/settoken rejected for non-owner user %s", user_id)
        return

    if not context.args:
        await update.message.reply_text("Usage: /settoken `<session_token>`", parse_mode="Markdown")
        return

    new_token = context.args[0]

    # Persist & update the in-memory client
    await save_token(new_token)
    if chatgpt_client is not None:
        await chatgpt_client.update_token(new_token)
    else:
        chatgpt_client = ChatGPTClient(new_token)
        await chatgpt_client.connect()

    # Delete the user's message to avoid leaking the token in chat
    try:
        await update.message.delete()
    except Exception:
        pass  # might lack delete permissions

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="✅ Session token updated and saved.",
    )
    logger.info("Session token updated by owner (user %s).", user_id)


# ── Message Handler ───────────────────────────────────────────────

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route non-command text messages to ChatGPT.

    Applies rate limiting, shows a typing indicator, and handles
    session-expired and generic errors gracefully.

    Args:
        update: Incoming Telegram update.
        context: Bot context.
    """
    global chatgpt_client

    user_id = update.effective_user.id
    text = update.message.text

    if not text:
        return

    # ── Rate limit ─────────────────────────────────────────────
    if _is_rate_limited(user_id):
        await update.message.reply_text("Please slow down ⏳")
        return

    # ── Guard: client must be initialised ──────────────────────
    if chatgpt_client is None:
        await update.message.reply_text(
            "⚠️ Bot is not ready — session token not loaded."
        )
        return

    # ── Typing indicator ───────────────────────────────────────
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action=ChatAction.TYPING,
    )

    conversation_id = user_conversations.get(user_id)

    try:
        response, new_conversation_id = await chatgpt_client.ask(
            prompt=text,
            conversation_id=conversation_id,
        )
        user_conversations[user_id] = new_conversation_id

        # Telegram messages have a 4096-char limit; split if needed
        for i in range(0, len(response), 4096):
            await update.message.reply_text(response[i : i + 4096])

    except SessionExpiredError:
        logger.error("Session expired while handling message from user %s", user_id)
        await update.message.reply_text(
            "⚠️ Session expired. Please update the token via /settoken"
        )

    except ChatGPTError as exc:
        logger.error("ChatGPT error for user %s: %s", user_id, exc)
        await update.message.reply_text(
            "❌ Something went wrong talking to ChatGPT. Please try again later."
        )

    except Exception as exc:
        logger.exception("Unhandled error for user %s: %s", user_id, exc)
        await update.message.reply_text(
            "❌ An unexpected error occurred. Please try again."
        )


async def handle_health_check(request):
    """Dummy health check endpoint for Render."""
    return web.Response(text="Bot is running!")

async def start_web_server():
    """Start a dummy aiohttp server to satisfy Render's port binding requirement."""
    app = web.Application()
    app.router.add_get('/', handle_health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"Dummy web server listening on port {port} for Render health checks.")


# ── Entrypoint ─────────────────────────────────────────────────────

async def post_init(application) -> None:
    """Callback executed after the Application is initialised.

    Loads the session token and creates the ChatGPT client.

    Args:
        application: The ``telegram.ext.Application`` instance.
    """
    global chatgpt_client

    token = await load_token()
    
    chatgpt_client = ChatGPTClient(session_token=token)
    await chatgpt_client.connect()
    logger.info("ChatGPT client ready.")
    
    # Start the dummy web server for Render
    await start_web_server()


def main() -> None:
    """Build and run the Telegram bot application."""
    logger.info("Starting ChatGPT Telegram Bot…")

    app = (
        ApplicationBuilder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .connect_timeout(30.0)
        .read_timeout(30.0)
        .write_timeout(30.0)
        .pool_timeout(30.0)
        .post_init(post_init)
        .build()
    )

    # Register handlers (order matters – commands first)
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("reset", cmd_reset))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("settoken", cmd_settoken))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Graceful shutdown on SIGINT / SIGTERM
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, lambda *_: None)  # let PTB handle it
        except (OSError, ValueError):
            pass  # SIGTERM may not be available on Windows

    logger.info("Bot is polling…")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()

