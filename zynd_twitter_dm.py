import streamlit as st
import gspread
import requests
import time
import random
import shutil
import asyncio
from oauth2client.service_account import ServiceAccountCredentials

# --- TWIKIT IMPORTS (PLAN A) ---
from twikit import Client

# --- SELENIUM IMPORTS (PLAN B) ---
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys

SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

def generate_twitter_dm(prospect_name, bio):
    headers = {
        "Authorization": f"Bearer {st.secrets['openrouter']['api_key']}",
        "Content-Type": "application/json"
    }
    prompt = f"""
    Act as Abhinav, a technical founder. Write a Twitter DM to a developer you just found.
    Lead Name/Handle: {prospect_name}
    Their Bio/Tweet Context: {bio}
    Rules:
    1. EXTREMELY short. 1-2 sentences maximum.
    2. Tone is super casual (Twitter style). No corporate speak.
    3. Mention you're building Zynd (a workspace for AI agents).
    4. Ask if they are open to checking it out.
    Return ONLY the exact text of the DM. No quotes, no intro, no labels.
    """
    data = {"model": "openai/gpt-4o-mini", "messages": [{"role": "user", "content": prompt}]}
    try:
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data, timeout=20)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content'].replace('"', '').strip()
        return None
    except:
        return None

# ==========================================
# PLAN A: TWIKIT API ENGINE
# ==========================================
async def try_api_send(handle, message):
    client = Client(language='en-US')
    client.set_cookies({
        'auth_token': st.secrets["twitter"]["auth_token"], 
        'ct0': st.secrets["twitter"]["ct0"]
    })
    user = await client.get_user_by_screen_name(handle)
    await client.send_dm(user.id, message)
    return True

# ==========================================
# PLAN B: SELENIUM STEALTH ENGINE
# ==========================================
def setup_stealth_browser():
    options = Options()
    options.add_argument('--headless=new')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    system_chromedriver = shutil.which("chromedriver")
    system_chromium = shutil.which("chromium") or shutil.which("chromium-browser")

    if system_chromedriver:
        if system_chromium: options.binary_location = system_chromium
        driver = webdriver.Chrome(service=Service(executable_path=system_chromedriver), options=options)
    else:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

def try_browser_send(driver, handle, message, status_container):
    driver.get(f"https://x.com/messages/compose?recipient_id={handle}")
    time.sleep(random.uniform(6.5, 9.2)) 
    
    # THE MODAL DESTROYER: Inject raw JS to instantly delete E2EE Passcode popups from the HTML
    try:
        driver.execute_script("""
            document.querySelectorAll('[role="dialog"]').forEach(e => e.remove());
            document.querySelectorAll('div[style*="background-color: rgba(0"]').forEach(e => e.remove());
        """)
        time.sleep(1)
    except:
        pass

    # Find the text box
    selectors = ['div[data-testid="dmComposerTextInput"]', 'div[data-testid="tweetTextarea_0"]']
    message_box = None
    for selector in selectors:
        try:
            message_box = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
            if message_box: break
        except: pass
    
    if not message_box:
        raise Exception("Message input box not found (DMs might be closed or blocked).")
    
    # Type out the message
    for char in message:
        message_box.send_keys(char)
        time.sleep(random.uniform(0.01, 0.05))
        
    time.sleep(random.uniform(1.0, 2.0))
    
    # Force click the send button via JavaScript to bypass any invisible overlays
    send_button = driver.find_element(By.CSS_SELECTOR, 'button[data-testid="dmComposerSendButton"]')
    driver.execute_script("arguments[0].click();", send_button)
    time.sleep(random.uniform(3.0, 4.5))
    return True

# ==========================================
# MASTER CONTROLLER
# ==========================================
def dispatch_twitter_dms(max_dms=5, mode="AI Generated", custom_msg="", status_container=None):
    if "twitter" not in st.secrets or "auth_token" not in st.secrets["twitter"] or "ct0" not in st.secrets["twitter"]:
        return 0, "Error: Missing Twitter tokens in Streamlit Secrets."

    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    
    try:
        sheet = client.open_by_key(SHEET_ID).worksheet("Twitter Leads")
        raw_data = sheet.get_all_values()
        if not raw_data or len(raw_data) < 2: return 0, "No leads found."
        headers = raw_data[0]
        cleaned_headers = [str(h).strip() if str(h).strip() else f"Unnamed_{idx}" for idx, h in enumerate(headers)]
        records = [dict(zip(cleaned_headers, row + [""] * (len(cleaned_headers) - len(row)))) for row in raw_data[1:]]
        status_col_idx = cleaned_headers.index("outreach_status") + 1 if "outreach_status" in cleaned_headers else None
    except Exception as e:
        return 0, f"Database Error: {str(e)}"
        
    dms_fired = 0
    api_is_broken = False # Master toggle
    driver = None
    
    for idx, row in enumerate(records):
        if dms_fired >= max_dms: break
            
        raw_handle = str(row.get("Tweet URL", row.get("Username", row.get("handle", row.get("User", ""))))).strip()
        if not raw_handle or "http" in raw_handle:
            url = str(row.get("Content", row.get("Profile URL", row.get("User URL", ""))))
            if "x.com/" in url or "twitter.com/" in url:
                parts = url.split("/")
                for i, p in enumerate(parts):
                    if p in ["x.com", "twitter.com"] and i + 1 < len(parts):
                        raw_handle = parts[i + 1]
                        break
                        
        handle = raw_handle.replace("@", "").split("?")[0].strip()
        if not handle or "http" in handle: continue
            
        status = str(row.get("outreach_status", "Pending")).strip()
        bio = str(row.get("Unnamed_6", row.get("bio", str(row.get("Content", ""))))).strip()
        if status in ["DM Sent", "DO NOT CONTACT 🛑", "DMs Closed / Failed", "Not Found"]: continue
            
        # 1. Draft Message
        if mode == "✍️ Custom Template":
            message = custom_msg.replace("{name}", handle).replace("{bio}", bio)
        else:
            if status_container: status_container.info(f"Drafting AI DM for @{handle}...")
            message = generate_twitter_dm(handle, bio)
        if not message: continue
            
        success = False
        
        # 2. ATTEMPT PLAN A (API)
        if not api_is_broken:
            if status_container: status_container.info(f"Attempting API delivery to @{handle}...")
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(try_api_send(handle, message))
                loop.close()
                success = True
                if status_container: status_container.success(f"API Success! Delivered to @{handle}.")
            except Exception as e:
                err_str = str(e).lower()
                if "key" in err_str or "clienttransaction" in err_str or "urls" in err_str:
                    if status_container: status_container.warning("Twitter API blockage detected! Failing over to Stealth Browser...")
                    api_is_broken = True # Permanently switch to Plan B for the rest of this run
                else:
                    if status_container: status_container.error(f"API Error for @{handle}: {e}")
                    if status_col_idx: sheet.update_cell(idx + 2, status_col_idx, "DMs Closed / Failed")
                    time.sleep(3)
                    continue
                    
        # 3. ATTEMPT PLAN B (BROWSER) IF API FAILED
        if api_is_broken and not success:
            if not driver:
                if status_container: status_container.warning("Booting Headless Chromium with Modal Destroyer...")
                driver = setup_stealth_browser()
                driver.get("https://x.com/robots.txt") 
                driver.add_cookie({'name': 'auth_token', 'value': st.secrets["twitter"]["auth_token"], 'domain': '.x.com', 'path': '/', 'secure': True})
                driver.add_cookie({'name': 'ct0', 'value': st.secrets["twitter"]["ct0"], 'domain': '.x.com', 'path': '/', 'secure': True})
            
            if status_container: status_container.info(f"Browser navigating to @{handle}'s inbox...")
            try:
                try_browser_send(driver, handle, message, status_container)
                success = True
                if status_container: status_container.success(f"Browser Success! Delivered to @{handle}.")
            except Exception as e:
                if status_container: status_container.error(f"Browser failed for @{handle}: {e}")
                if status_col_idx: sheet.update_cell(idx + 2, status_col_idx, "DMs Closed / Failed")
                time.sleep(3)
                continue

        # 4. POST-SEND LOGGING & DELAYS
        if success:
            dms_fired += 1
            if status_col_idx: sheet.update_cell(idx + 2, status_col_idx, "DM Sent")
            try:
                import zynd_outreach_history
                zynd_outreach_history.log_outreach_event(handle, "Abhinav", "Twitter / X (Hybrid)", "Initial Pitch", message)
            except: pass
            
            if dms_fired < max_dms:
                delay = random.randint(90, 180) if api_is_broken else random.randint(50, 90)
                if status_container: status_container.success(f"Sleeping {delay}s to avoid rate limits...")
                time.sleep(delay)
                
    if driver: driver.quit()
    return dms_fired, f"Omni-Engine Cycle Concluded. Sent {dms_fired} messages."