# Nemo (ChatGPT Telegram Bot)

A personal Telegram bot that forwards your messages to ChatGPT using a browser session token — **no OpenAI API key required**.

> ⚠️ **Disclaimer**: This project uses a reverse-engineered, unofficial ChatGPT API. It is intended for **personal use only** and likely violates [OpenAI's Terms of Service](https://openai.com/policies/terms-of-use). Use at your own risk.

---

## Features

| Feature | Description |
|---|---|
| 💬 Conversational | Maintains per-user conversation threads |
| 🔄 `/reset` | Start a fresh conversation at any time |
| 📊 `/status` | Check bot health and token status |
| 🔑 `/settoken` | Hot-swap the session token without restarting (owner only) |
| ⏳ Rate limiting | Prevents message spam (configurable) |
| 🐳 Docker-ready | One-command deployment with `docker compose` |
| 💾 Token persistence | Session token survives restarts via a JSON file |

---

## Prerequisites

- **Python 3.11+** (or Docker)
- A **Telegram Bot Token** from [@BotFather](https://t.me/BotFather)
- A **ChatGPT session token** from your browser
- Your **Telegram user ID**

---

## 1. Get Your ChatGPT Session Token

The bot authenticates with ChatGPT using the `__Secure-next-auth.session-token` cookie from your browser.

1. Open [https://chat.openai.com](https://chat.openai.com) and log in.
2. Open **Developer Tools** (`F12` or `Ctrl+Shift+I`).
3. Go to the **Application** tab (Chrome) or **Storage** tab (Firefox).
4. In the left sidebar, expand **Cookies** → click `https://chat.openai.com`.
5. Find the cookie named **`__Secure-next-auth.session-token`**.
6. Copy its **Value** — this is your session token.

> 💡 This token expires periodically (typically every few days). When it does, the bot will notify you and you can update it via `/settoken`.

---

## 2. Create a Telegram Bot

1. Open Telegram and search for **@BotFather**.
2. Send `/newbot` and follow the prompts.
3. BotFather will give you a **bot token** like `123456789:ABCdefGhIjKlMnOpQrStUvWxYz`.
4. Save this token — you'll need it for the `.env` file.

---

## 3. Find Your Telegram User ID

1. Search for **@userinfobot** on Telegram.
2. Send it any message.
3. It will reply with your **user ID** (a number like `123456789`).

This is needed for `OWNER_USER_ID` so only you can use the `/settoken` command.

---

## 4. Setup

### Clone and configure

```bash
git clone <your-repo-url>
cd nemo

# Create your .env file from the template
cp .env.example .env
```

Edit `.env` and fill in your values:

```dotenv
TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIjKlMnOpQrStUvWxYz
CHATGPT_SESSION_TOKEN=eyJhbGciOi...your_long_token_here
OWNER_USER_ID=123456789
SESSION_FILE=session_data.json
RATE_LIMIT_SECONDS=3
```

### Option A: Run with Docker (recommended)

```bash
docker compose up -d --build
```

View logs:
```bash
docker compose logs -f chatgpt-bot
```

### Option B: Run directly with Python

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
python bot.py
```

---

## 5. Usage

| Command | Description |
|---|---|
| `/start` | Show the welcome message |
| `/reset` | Clear conversation history and start fresh |
| `/status` | Display bot status and token info |
| `/settoken <token>` | Update the session token at runtime (owner only) |
| _any text_ | Send to ChatGPT and get a response |

---

## 6. Refreshing the Session Token

When your session token expires, the bot will respond with:

> ⚠️ Session expired. Please update the token via /settoken

To refresh:

1. Repeat the steps in [section 1](#1-get-your-chatgpt-session-token) to get a new token.
2. Send `/settoken <new_token>` to the bot in Telegram.
3. The token is saved to disk automatically and will survive restarts.

Alternatively, you can update the `.env` file and restart the bot.

---

## Project Structure

```
nemo/
├── bot.py               # Main Telegram bot — handlers, polling
├── chatgpt_client.py    # ChatGPT session wrapper (re_gpt)
├── session_manager.py   # Token persistence & refresh logic
├── config.py            # Environment config loader
├── .env.example         # Template for secrets
├── requirements.txt     # Python dependencies
├── Dockerfile           # Container build instructions
├── docker-compose.yml   # One-command deployment
└── README.md            # This file
```

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `Session expired` error | Get a new token from your browser and use `/settoken` |
| Bot not responding | Check logs with `docker compose logs -f` or terminal output |
| `Missing required environment variable` | Make sure your `.env` file has all required values |
| Rate limited | Wait a few seconds between messages (default: 3s) |

---

## License

This project is for personal, educational use only. No warranty is provided.
