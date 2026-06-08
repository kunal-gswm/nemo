"""ChatGPT session wrapper using undetected-chromedriver automation.

Provides a thin async interface around a headless Chromium instance
to bypass Cloudflare and Arkose protections by simulating a real browser.
"""

from __future__ import annotations

import logging
import asyncio
from typing import Optional, Tuple
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

logger = logging.getLogger(__name__)


# ── Custom Exceptions ──────────────────────────────────────────────

class ChatGPTError(Exception):
    """Generic wrapper for any ChatGPT-related failure."""


class SessionExpiredError(ChatGPTError):
    """Raised when the session token has expired or been revoked."""


# ── Client ─────────────────────────────────────────────────────────

class ChatGPTClient:
    """Async wrapper around undetected-chromedriver to control ChatGPT.

    Manages the browser lifecycle so callers can
    simply call ``await client.ask(prompt)``.
    """

    def __init__(self, session_token: str) -> None:
        """Initialise the client.

        Args:
            session_token: ``__Secure-next-auth.session-token`` cookie.
        """
        self._session_token: str = session_token
        self._driver: Optional[uc.Chrome] = None
        logger.info("ChatGPTClient initialised with undetected-chromedriver.")

    def _sync_connect(self):
        """Synchronous part of connect."""
        if self._driver is not None:
            try:
                self._driver.quit()
            except Exception:
                pass
                
        options = uc.ChromeOptions()
        # Turnstile strongly blocks headless=new, so we must run visibly.
        options.add_argument("--window-size=1280,720")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        
        import platform
        if platform.system() == "Windows":
            self._driver = uc.Chrome(options=options, version_main=148)
        else:
            self._driver = uc.Chrome(options=options)
        
        # We need to navigate to the domain first to set cookies
        self._driver.set_page_load_timeout(30)
        
        try:
            self._driver.get("https://chatgpt.com/404")
        except TimeoutException:
            pass # We don't care if the 404 page times out, we just need the domain
            
        # Inject the auth cookie
        token = self._session_token.strip()
        chunk_size = 3933
        chunks = [token[i:i+chunk_size] for i in range(0, len(token), chunk_size)]
        
        if len(chunks) == 1:
            self._driver.add_cookie({
                "name": "__Secure-next-auth.session-token",
                "value": chunks[0],
                "domain": "chatgpt.com",
                "path": "/"
            })
        else:
            for i, chunk in enumerate(chunks):
                self._driver.add_cookie({
                    "name": f"__Secure-next-auth.session-token.{i}",
                    "value": chunk,
                    "domain": "chatgpt.com",
                    "path": "/"
                })
                
        # Now go to the actual page
        logger.info("Navigating to chatgpt.com...")
        try:
            self._driver.get("https://chatgpt.com/")
        except TimeoutException:
            logger.warning("driver.get() timed out. Page might be infinitely loading.")
        
        # Check for login
        try:
            WebDriverWait(self._driver, 15).until(
                EC.presence_of_element_located((By.ID, "prompt-textarea"))
            )
            logger.info("Session connected and logged in.")
        except TimeoutException:
            url = self._driver.current_url.lower()
            try:
                self._driver.save_screenshot("error_screenshot.png")
                logger.info("Saved error_screenshot.png for debugging.")
            except Exception as e:
                logger.error(f"Failed to save screenshot: {e}")
                
            if "login" in url:
                raise SessionExpiredError("Session token appears to be invalid or expired. Redirected to login.")
            else:
                logger.warning(f"Could not find prompt textarea. URL: {url}")
                raise ChatGPTError("Failed to load ChatGPT interface. Screenshot saved.")

    async def connect(self) -> None:
        """Launch the browser and navigate to ChatGPT."""
        if not self._session_token:
            raise ChatGPTError("No session_token provided.")
            
        logger.info("Starting undetected-chromedriver...")
        await asyncio.to_thread(self._sync_connect)

    def _sync_disconnect(self):
        if self._driver:
            try:
                self._driver.quit()
            except Exception:
                pass
            self._driver = None

    async def disconnect(self) -> None:
        """Close the browser context."""
        await asyncio.to_thread(self._sync_disconnect)
        logger.info("Session disconnected.")

    async def update_token(self, session_token: str) -> None:
        """Hot-swap credentials and reconnect."""
        self._session_token = session_token
        await self.connect()
        logger.info("Token updated and reconnected.")

    def _sync_ask(self, prompt: str, conversation_id: Optional[str]) -> Tuple[str, str]:
        if not self._driver:
            raise ChatGPTError("Driver not initialized.")
            
        # If continuing a conversation, navigate to that URL
        if conversation_id and self._driver.current_url != conversation_id:
            logger.info(f"Navigating to conversation {conversation_id}")
            self._driver.get(conversation_id)
            WebDriverWait(self._driver, 15).until(
                EC.presence_of_element_located((By.ID, "prompt-textarea"))
            )

        # Wait for textarea
        textarea = WebDriverWait(self._driver, 15).until(
            EC.element_to_be_clickable((By.ID, "prompt-textarea"))
        )
        
        # Fill the prompt
        textarea.send_keys(prompt)
        
        # Click send
        send_btn = WebDriverWait(self._driver, 5).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, '[data-testid="send-button"]'))
        )
        send_btn.click()
        
        # Wait for generation to finish robustly
        import time
        last_text = None
        stable_count = 0
        
        logger.info("Waiting for generation to finish...")
        time.sleep(2) # Give it a moment to spawn the response container
        
        response_text = ""
        for _ in range(60): # Max 120 seconds
            assistants = self._driver.find_elements(By.CSS_SELECTOR, '[data-message-author-role="assistant"]')
            if not assistants:
                time.sleep(2)
                continue
                
            current_text = assistants[-1].text
            
            # Check if stop button is present
            stop_btns = self._driver.find_elements(By.CSS_SELECTOR, '[data-testid="stop-button"]')
            is_generating = len(stop_btns) > 0
            
            if current_text and current_text == last_text and not is_generating:
                stable_count += 1
                if stable_count >= 2: # Stable for 4 seconds and no stop button
                    response_text = current_text
                    break
            else:
                stable_count = 0
                last_text = current_text
                
            time.sleep(2)
            
        if not response_text and assistants:
            response_text = assistants[-1].text
            
        if not response_text:
            raise ChatGPTError("ChatGPT returned an empty response or timed out.")
        
        new_conversation_id = self._driver.current_url
        
        logger.info(
            "ChatGPT responded (conversation=%s, length=%d)",
            new_conversation_id,
            len(response_text),
        )
        return response_text, new_conversation_id

    async def ask(
        self,
        prompt: str,
        conversation_id: Optional[str] = None,
    ) -> Tuple[str, str]:
        """Send a prompt to ChatGPT and return the reply."""
        if self._driver is None:
            await self.connect()

        try:
            return await asyncio.to_thread(self._sync_ask, prompt, conversation_id)
        except Exception as exc:
            logger.exception("Unexpected error during ask: %s", exc)
            raise ChatGPTError(str(exc))
