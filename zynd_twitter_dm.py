import streamlit as st
import gspread
import requests
import time
import random
import re
import shutil
import traceback
from oauth2client.service_account import ServiceAccountCredentials

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium_stealth import stealth

SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

def generate_twitter_dm(prospect_name, bio, status_container):
    """Generates the highly-constrained founder-style cold DM payload."""
    headers = {
        "Authorization": f"Bearer {st.secrets['openrouter']['api_key']}",
        "Content-Type": "application/json"
    }
    
    prompt = f"""
    You are Abhinav, a highly technical founder reaching out to a developer on X.
    Target Context: {bio}

    Draft a casual DM. You MUST use this exact fill-in-the-blank structure:
    [Short 3-5 word observation] + " building zynd (agent os) btw." + [1 short technical question]

    STRICT RULES:
    1. ALL LOWERCASE.
    2. NEVER start with an "@" symbol, a name, or a greeting.
    3. YOU MUST MENTION "zynd". 
    4. No punctuation at the very end of the message.
    5. MAX 25 WORDS total.
    """
    
    data = {
        "model": "openai/gpt-4o-mini", 
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2
    }
    
    try:
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data, timeout=15)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content'].replace('"', '').strip()
        else:
            if status_container: status_container.error(f"OpenRouter API Error: {response.text}")
    except Exception as e:
        if status_container: status_container.error(f"AI Generation Failed: {str(e)}")
    return None

def setup_stealth_browser():
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    sys_chromedriver = shutil.which("chromedriver")
    sys_chromium = shutil.which("chromium") or shutil.which("chromium-browser")
    
    if sys_chromium and sys_chromedriver:
        options.binary_location = sys_chromium
        service = Service(executable_path=sys_chromedriver)
    else:
        from webdriver_manager.chrome import ChromeDriverManager
        service = Service(ChromeDriverManager().install())
        
    driver = webdriver.Chrome(service=service, options=options)
    
    stealth(driver,
        languages=["en-US", "en"],
        vendor="Google Inc.",
        platform="MacIntel",
        webgl_vendor="Intel Inc.",
        renderer="Intel Iris OpenGL Engine",
        fix_hairline=True,
    )
    
    return driver

def try_browser_send(driver, handle, message, status_container):
    try:
        # 1. Profile Routing
        driver.get(f"https://x.com/{handle}")
        time.sleep(random.uniform(7.0, 10.0))
        
        if status_container: status_container.info(f"Scanning @{handle}'s profile...")

        # 2. Click DM Button
        try:
            dm_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, '[data-testid="sendDMFromProfile"]'))
            )
            driver.execute_script("arguments[0].click();", dm_btn)
        except:
            raise Exception("No DM button found. DMs are likely closed.")

        time.sleep(random.uniform(4.0, 6.0))

        # 3. Find Draft.js Chat Box
        message_box = None
        selectors = ['div[data-testid="dmComposerTextInput"]', 'div.public-DraftEditor-content', 'div[role="textbox"]']
        
        for selector in selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elements:
                    if el.is_displayed():
                        message_box = el
                        break
                if message_box: break
            except: pass
            
        if not message_box:
            raise Exception("Chat interface failed to render.")
            
        # 4. Type and Send
        driver.execute_script("arguments[0].focus();", message_box)
        for char in message:
            message_box.send_keys(char)
            time.sleep(random.uniform(0.01, 0.05))
            
        time.sleep(1.0)
        message_box.send_keys(Keys.RETURN)
        time.sleep(random.uniform(3.0, 4.5))
        return True
        
    except Exception as e:
        try:
            driver.save_screenshot("cloud_browser_debug.png")
            if status_container: status_container.image("cloud_browser_debug.png")
        except: pass
            
        raise Exception(f"Execution Error: {str(e)}")

def dispatch_twitter_dms(max_dms=5, mode="AI Generated", custom_msg="", status_container=None):
    tw_auth = st.secrets.get("twitter", {}).get("auth_token", "")
    tw_ct0 = st.secrets.get("twitter", {}).get("ct0", "")
    
    if not tw_auth or not tw_ct0:
        return 0, "Error: Missing Twitter tokens."

    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    
    try:
        sheet = client.open_by_key(SHEET_ID).worksheet("Twitter Leads")
        raw_data = sheet.get_all_records()
        status_col_name = next((h for h in ["outreach_status", "Status", "status"] if h in raw_data[0].keys()), None)
    except Exception as e:
        return 0, f"Database Error: {str(e)}"
        
    dms_fired = 0
    driver = None
    
    for idx, row in enumerate(raw_data):
        if dms_fired >= max_dms: break
            
        raw_handle = str(row.get("Tweet URL", row.get("Username", row.get("handle", "")))).strip()
        handle = raw_handle.replace("@", "").split("?")[0].strip()
        status = str(row.get(status_col_name, "")).strip().lower() if status_col_name else ""
        
        if not handle or "http" in handle or "sent" in status: continue
            
        message = custom_msg.replace("{name}", handle) if mode == "✍️ Custom Template" else generate_twitter_dm(handle, row.get("bio", ""), status_container)
        if not message: continue
            
        if not driver:
            if status_container: status_container.warning("Booting Stealth Browser...")
            driver = setup_stealth_browser()
            driver.get("https://x.com/robots.txt") 
            driver.add_cookie({'name': 'auth_token', 'value': tw_auth, 'domain': '.x.com', 'path': '/', 'secure': True})
            driver.add_cookie({'name': 'ct0', 'value': tw_ct0, 'domain': '.x.com', 'path': '/', 'secure': True})

        try:
            # FIX: We now include status_container here
            try_browser_send(driver, handle, message, status_container)
            
            dms_fired += 1
            if status_col_name: sheet.update_cell(idx + 2, list(row.keys()).index(status_col_name) + 1, "DM Sent")
            if status_container: status_container.success(f"✅ Sent to @{handle}.")
            time.sleep(random.randint(45, 90))
        except Exception as e:
            if status_container: 
                st.error(f"🚨 **Execution Failure for @{handle}** 🚨")
                st.markdown(str(e))
            time.sleep(3)
            continue
            
    if driver: driver.quit()
    return dms_fired, f"Cycle Concluded. Sent {dms_fired} messages."