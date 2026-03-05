"""
auto_login.py — Fully automated Zerodha login using TOTP (no manual steps)

How it works:
  1. Opens Zerodha login page using a headless Chrome browser (Selenium)
  2. Enters your user ID and password automatically
  3. Generates a TOTP code from your secret (same as your authenticator app)
  4. Submits the TOTP, extracts the request_token from the redirect URL
  5. Exchanges request_token for access_token and saves it

Run this script every morning before market open (cron job handles this).

Requirements:
    pip install selenium pyotp requests webdriver-manager

One-time setup on VPS:
    sudo apt install chromium-browser chromium-chromedriver -y
"""

import os
import sys
import json
import time
import logging
import pyotp
import requests
from datetime import date
from urllib.parse import urlparse, parse_qs
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from kiteconnect import KiteConnect

import config

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# HEADLESS CHROME SETUP
# ─────────────────────────────────────────────

def get_driver():
    """Set up headless Chromium for running on VPS (no display needed)."""
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1280,800")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])

    # Try system chromedriver first (installed via apt on VPS)
    try:
        service = Service("/usr/bin/chromedriver")
        driver  = webdriver.Chrome(service=service, options=options)
        return driver
    except Exception:
        pass

    # Fallback: use webdriver-manager to auto-download
    try:
        from webdriver_manager.chrome import ChromeDriverManager
        service = Service(ChromeDriverManager().install())
        driver  = webdriver.Chrome(service=service, options=options)
        return driver
    except Exception as e:
        logger.error(f"Could not start Chrome driver: {e}")
        raise


# ─────────────────────────────────────────────
# TOTP GENERATOR
# ─────────────────────────────────────────────

def generate_totp(totp_secret: str) -> str:
    """Generate current 6-digit TOTP code from secret."""
    totp = pyotp.TOTP(totp_secret)
    return totp.now()


# ─────────────────────────────────────────────
# AUTOMATED LOGIN
# ─────────────────────────────────────────────

def auto_login() -> KiteConnect:
    """
    Fully automated Zerodha login.
    Returns authenticated KiteConnect instance.
    """
    # Check if today's token already exists
    token_data = _load_token()
    if token_data and token_data.get("date") == str(date.today()):
        logger.info("✓ Valid token already exists for today. Skipping login.")
        kite = KiteConnect(api_key=config.KITE_API_KEY)
        kite.set_access_token(token_data["access_token"])
        return kite

    logger.info("Starting automated Zerodha login...")

    kite       = KiteConnect(api_key=config.KITE_API_KEY)
    login_url  = kite.login_url()
    driver     = None

    try:
        driver = get_driver()
        wait   = WebDriverWait(driver, 20)

        # ── Step 1: Open login page ──
        logger.info("Opening Zerodha login page...")
        driver.get(login_url)
        time.sleep(2)

        # ── Step 2: Enter User ID ──
        logger.info("Entering user ID...")
        user_id_field = wait.until(
            EC.presence_of_element_located((By.ID, "userid"))
        )
        user_id_field.clear()
        user_id_field.send_keys(config.ZERODHA_USER_ID)
        time.sleep(0.5)

        # ── Step 3: Enter Password ──
        logger.info("Entering password...")
        password_field = driver.find_element(By.ID, "password")
        password_field.clear()
        password_field.send_keys(config.ZERODHA_PASSWORD)
        time.sleep(0.5)

        # ── Step 4: Click Login ──
        login_btn = driver.find_element(By.XPATH, '//button[@type="submit"]')
        login_btn.click()
        time.sleep(3)

        # ── Step 5: Enter TOTP ──
        logger.info("Entering TOTP code...")
        totp_code = generate_totp(config.ZERODHA_TOTP_SECRET)
        logger.info(f"  Generated TOTP: {totp_code}")

        totp_field = wait.until(
            EC.presence_of_element_located((By.XPATH,
                '//input[@type="number" or @label="External TOTP" or @id="totp"]'
            ))
        )
        totp_field.clear()
        totp_field.send_keys(totp_code)
        time.sleep(0.5)

        # ── Step 6: Submit TOTP ──
        try:
            submit_btn = driver.find_element(By.XPATH, '//button[@type="submit"]')
            submit_btn.click()
        except Exception:
            pass  # Sometimes auto-submits after 6 digits

        # ── Step 7: Wait for redirect and extract request_token ──
        logger.info("Waiting for redirect...")
        time.sleep(5)

        request_token = _extract_request_token(driver.current_url)

        if not request_token:
            # Try waiting a bit more
            time.sleep(5)
            request_token = _extract_request_token(driver.current_url)

        if not request_token:
            logger.error(f"Could not extract request_token. Current URL: {driver.current_url}")
            raise ValueError("request_token not found in redirect URL")

        logger.info(f"✓ Got request_token: {request_token[:10]}...")

        # ── Step 8: Exchange for access_token ──
        session      = kite.generate_session(request_token, api_secret=config.KITE_API_SECRET)
        access_token = session["access_token"]
        kite.set_access_token(access_token)

        _save_token(access_token)
        logger.info("✓ Auto-login successful! Access token saved.")

        return kite

    except Exception as e:
        logger.error(f"Auto-login failed: {e}")
        # Send Telegram alert if configured
        try:
            from alerts import alert_error
            alert_error(f"Auto-login failed: {e}")
        except Exception:
            pass
        raise

    finally:
        if driver:
            driver.quit()


def _extract_request_token(url: str) -> str:
    """Extract request_token from redirect URL."""
    try:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        tokens = params.get("request_token", [])
        return tokens[0] if tokens else ""
    except Exception:
        return ""


def _save_token(access_token: str):
    os.makedirs(os.path.dirname(config.ACCESS_TOKEN_FILE) or ".", exist_ok=True)
    data = {"date": str(date.today()), "access_token": access_token}
    with open(config.ACCESS_TOKEN_FILE, "w") as f:
        json.dump(data, f)


def _load_token():
    try:
        with open(config.ACCESS_TOKEN_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


# ─────────────────────────────────────────────
# ENTRY POINT (run standalone to test)
# ─────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("logs/login.log")
        ]
    )
    os.makedirs("logs", exist_ok=True)

    try:
        kite    = auto_login()
        profile = kite.profile()
        print(f"\n✓ Logged in as: {profile['user_name']} ({profile['user_id']})")
    except Exception as e:
        print(f"\n✗ Login failed: {e}")
        sys.exit(1)
