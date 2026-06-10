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
from selenium_stealth import stealth
from selenium.webdriver.common.action_chains import ActionChains

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
        # 1. Profile Routing (The Human Way)
        driver.get(f"https://x.com/{handle}")
        time.sleep(random.uniform(6.0, 9.0))
        
        if status_container: status_container.info(f"Scanning @{handle}'s profile for DM button...")

        # 2. Click DM Button on Profile
        try:
            dm_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, '[data-testid="sendDMFromProfile"]'))
            )
            driver.execute_script("arguments[0].click();", dm_btn)
        except:
            raise Exception("No DM button found. DMs are closed or they do not follow you.")

        time.sleep(random.uniform(3.0, 5.0))

        # 3. Safely Close Tooltips (Without destroying the chat box)
        try:
            driver.execute_script("""
                let closeBtns = document.querySelectorAll('div[aria-label="Close"]');
                closeBtns.forEach(b => b.click());
            """)
        except: pass

        # 4. Target the Draft.js framework directly (Discovered from your HTML logs)
        selectors = [
            'div[data-testid="dmComposerTextInput"]',
            'div.public-DraftEditor-content',
            'aside[aria-label="Start a new message"] div[role="textbox"]',
            'div[role="textbox"]'
        ]
        
        message_box = None
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
            raise Exception("Chat interface failed to render. Twitter layout shifted.")
            
        if status_container: status_container.info(f"Typing payload to @{handle}...")
        
        # 5. Type and Send (with bulletproof ActionChains fallback)
        try:
            # Force focus using JavaScript
            driver.execute_script("arguments[0].focus();", message_box)
            time.sleep(0.5)
            
            for char in message:
                message_box.send_keys(char)
                time.sleep(random.uniform(0.01, 0.05))
                
            time.sleep(1.0)
            message_box.send_keys(Keys.RETURN)
        except:
            # Absolute Fallback: If standard send_keys fails, force typing via ActionChains
            ActionChains(driver).send_keys(message).send_keys(Keys.RETURN).perform()
            
        time.sleep(random.uniform(3.0, 4.5))
        return True
        
    except Exception as e:
        try:
            driver.save_screenshot("cloud_browser_debug.png")
            if status_container: status_container.image("cloud_browser_debug.png")
        except: pass
            
        current_url = driver.current_url
        raise Exception(f"**Current URL:** {current_url}\n\n**Error:** {str(e)}")

def dispatch_twitter_dms(max_dms=5, mode="AI Generated", custom_msg="", status_container=None):
    tw_auth = st.secrets.get("twitter", {}).get("auth_token", "")
    tw_ct0 = st.secrets.get("twitter", {}).get("ct0", "")
    
    if not tw_auth or not tw_ct0:
        return 0, "Error: Missing Twitter tokens in Streamlit Secrets."

    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    
    try:
        sheet = client.open_by_key(SHEET_ID).worksheet("Twitter Leads")
        raw_data = sheet.get_all_values()
        if not raw_data or len(raw_data) < 2: return 0, "No leads found."
            
        headers = [str(h).strip() if str(h).strip() else f"Unnamed_{idx}" for idx, h in enumerate(raw_data[0])]
        records = [dict(zip(headers, row + [""] * (len(headers) - len(row)))) for row in raw_data[1:]]
        
        status_col_name = next((h for h in ["outreach_status", "Status", "status"] if h in headers), None)
        status_col_idx = headers.index(status_col_name) + 1 if status_col_name else None
    except Exception as e:
        return 0, f"Database Error: {str(e)}"
        
    dms_fired = 0
    driver = None
    
    for idx, row in enumerate(records):
        if dms_fired >= max_dms: break
            
        raw_handle = str(row.get("Tweet URL", row.get("Username", row.get("handle", row.get("User", ""))))).strip()
        handle = raw_handle.replace("@", "").split("?")[0].strip()
        
        if not handle or "http" in handle: continue
            
        status = str(row.get(status_col_name, "Pending")).strip().lower() if status_col_name else "pending"
        bio = str(row.get("Unnamed_6", row.get("bio", str(row.get("Content", ""))))).strip()
        
        if any(kw in status for kw in ["sent", "stop", "failed", "closed"]): continue
            
        # 1. Draft Message
        if status_container: status_container.info(f"🧠 AI Context Engine analyzing @{handle}...")
        
        if mode == "✍️ Custom Template":
            message = custom_msg.replace("{name}", handle).replace("{bio}", bio)
        else:
            message = generate_twitter_dm(handle, bio, status_container)
            
        if not message: 
            if status_container: status_container.warning(f"Skipping @{handle} because message generation failed.")
            time.sleep(2)
            continue
            
        # 2. Boot Cloud Browser
        if not driver:
            if status_container: status_container.warning("Booting Stealth Browser... Please wait.")
            try:
                driver = setup_stealth_browser()
                driver.get("https://x.com/robots.txt") 
                driver.add_cookie({'name': 'auth_token', 'value': tw_auth, 'domain': '.x.com', 'path': '/', 'secure': True})
                driver.add_cookie({'name': 'ct0', 'value': tw_ct0, 'domain': '.x.com', 'path': '/', 'secure': True})
            except Exception as e:
                error_trace = traceback.format_exc()
                if status_container: status_container.error(f"Browser Boot Failed:\n```python\n{error_trace}\n```")
                return dms_fired, "Failed to start browser."

        if status_container: status_container.info(f"Browser navigating to @{handle}'s inbox...")
        
        # 3. Fire Payload
        try:
            try_browser_send(driver, handle, message)
            dms_fired += 1
            if status_col_idx: sheet.update_cell(idx + 2, status_col_idx, "DM Sent")
            if status_container: status_container.success(f"✅ Browser Success! Delivered to @{handle}.")
            
            if dms_fired < max_dms:
                delay = random.randint(45, 75)
                if status_container: status_container.write(f"⏳ Sleeping {delay}s...")
                time.sleep(delay)
                
        except Exception as e:
            if status_container: 
                # This will print the massive diagnostic block we created above
                st.error(f"🚨 **Execution Failure for @{handle}** 🚨")
                st.markdown(str(e))
                
            if status_col_idx: sheet.update_cell(idx + 2, status_col_idx, "DMs Closed / Failed")
            time.sleep(3)
            continue
            
    if driver: driver.quit()
    return dms_fired, f"Cloud Browser Engine Concluded. Sent {dms_fired} messages."