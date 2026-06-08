import time
import undetected_chromedriver as uc
import logging
import sys

logger = logging.getLogger(__name__)

def login_and_get_token() -> str:
    logger.info("Opening a visible browser so you can log in to ChatGPT...")
    print("\n" + "="*60)
    print("ACTION REQUIRED: Please log in to ChatGPT in the browser window that just opened.")
    print("If you successfully log in, this script will grab your session token and close the browser automatically.")
    print("="*60 + "\n")
    
    options = uc.ChromeOptions()
    
    try:
        driver = uc.Chrome(options=options, version_main=148)
    except Exception as e:
        print(f"Error starting Chrome: {e}")
        return None
        
    driver.get("https://chatgpt.com/")
    
    token = None
    
    while True:
        time.sleep(2)
        try:
            cookies = driver.get_cookies()
        except Exception:
            # Browser might have been closed manually
            break
            
        token_chunks = {}
        single_token = None
        
        for cookie in cookies:
            name = cookie.get('name', '')
            val = cookie.get('value', '')
            if name == "__Secure-next-auth.session-token":
                single_token = val
            elif name.startswith("__Secure-next-auth.session-token."):
                try:
                    idx = int(name.split(".")[-1])
                    token_chunks[idx] = val
                except ValueError:
                    pass
                    
        if single_token:
            token = single_token
            break
        elif token_chunks:
            token = "".join(token_chunks[i] for i in sorted(token_chunks.keys()))
            break
            
    if token:
        print("\nSuccessfully captured session token from browser!")
    else:
        print("\nFailed to capture token or browser closed early.")
        
    try:
        driver.quit()
    except Exception:
        pass
    return token

def update_env_file(token: str):
    import os
    env_path = ".env"
    lines = []
    updated = False
    
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
    for i, line in enumerate(lines):
        if line.startswith("CHATGPT_SESSION_TOKEN="):
            lines[i] = f"CHATGPT_SESSION_TOKEN={token}\n"
            updated = True
            break
            
    if not updated:
        lines.append(f"CHATGPT_SESSION_TOKEN={token}\n")
        
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(lines)
        
    print("Updated .env with new token.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    token = login_and_get_token()
    if token:
        update_env_file(token)
        sys.exit(0)
    else:
        sys.exit(1)
