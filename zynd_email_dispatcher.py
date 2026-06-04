import streamlit as st
import gspread
import requests
import smtplib
import time
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from oauth2client.service_account import ServiceAccountCredentials

# --- ENVIRONMENT PARAMETERS ---
SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'
OPENROUTER_API_KEY = st.secrets["openrouter"]["api_key"]

def generate_personalized_payload(prospect_name, context_signal, bio):
    """Hits OpenRouter to craft a completely unique cold email based on user metadata."""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    prompt = f"""
    You are a technical founder contacting an open-source engineer. Write a highly personalized, casual, short cold email.
    Prospect Name: {prospect_name}
    Signal Caught: {context_signal}
    Prospect Bio: {bio}
    
    Rules:
    1. Keep it under 4 sentences. Sound like a engineer, not a marketer.
    2. Mention their specific work/signal casually.
    3. Pitch Zynd: A devtool/growth workspace that helps autonomous AI agents get discovered and integrated.
    4. End with a low-friction question.
    5. Return a strict raw string in this EXACT layout format:
    SUBJECT: [Insert Subject Line Here]
    BODY: [Insert Email Body Here]
    """
    
    data = {
        "model": "google/gemini-2.5-flash",
        "messages": [{"role": "user", "content": prompt}]
    }
    
    try:
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data, timeout=15)
        if response.status_code == 200:
            ai_text = response.json()['choices'][0]['message']['content']
            if "SUBJECT:" in ai_text and "BODY:" in ai_text:
                subject = ai_text.split("SUBJECT:")[1].split("BODY:")[0].strip()
                body = ai_text.split("BODY:")[1].strip()
                return subject, body
        return "Quick question regarding your agent work", f"Hey {prospect_name},\n\nI saw your work on GitHub. I'm building Zynd to help agents get discovered. Let me know if you're open to a quick look."
    except Exception:
        return "Quick question regarding your agent work", f"Hey {prospect_name},\n\nI saw your work on GitHub. I'm building Zynd to help agents get discovered. Let me know if you're open to a quick look."

def dispatch_campaign(max_emails=10, status_container=None):
    """Scans databases, drafts personalization layers, fires via SMTP, and logs updates."""
    # Validate Secrets immediately to prevent crashes
    if "smtp" not in st.secrets:
        return 0, "Error: [smtp] secrets block is missing from Streamlit Cloud."

    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    
    sheet = client.open_by_key(SHEET_ID).worksheet("github_stargazer_leads")
    records = sheet.get_all_records()
    
    if not records: return 0, "No leads located inside the target database."

    smtp_server = st.secrets["smtp"]["server"]
    smtp_port = int(st.secrets["smtp"]["port"])
    sender_email = st.secrets["smtp"]["email"]
    sender_password = st.secrets["smtp"]["password"]

    emails_fired = 0
    
    for idx, row in enumerate(records):
        if emails_fired >= max_emails:
            break
            
        prospect_email = str(row.get("public_email", "")).strip()
        status = str(row.get("outreach_status", "Pending")).strip()
        username = str(row.get("github_username", "Developer")).strip()
        bio = str(row.get("bio", "")).strip()
        signal = str(row.get("source_repo", "GitHub")).strip()
        
        # Guardrail Filter
        if not prospect_email or "@" not in prospect_email or "noreply" in prospect_email.lower():
            continue
        if status in ["Message 1 Sent", "DO NOT CONTACT 🛑", "Replied - Interested"]:
            continue
            
        if status_container: status_container.info(f"Drafting AI payload for {username}...")
        
        subject, body = generate_personalized_payload(username, signal, bio)
        
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = prospect_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        try:
            if status_container: status_container.warning(f"Connecting to SMTP server... firing email to {prospect_email}")
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, prospect_email, msg.as_string())
            server.quit()
            
            emails_fired += 1
            row_num = idx + 2
            
            # Update CRM
            headers = sheet.row_values(1)
            if "outreach_status" in headers:
                sheet.update_cell(row_num, headers.index("outreach_status") + 1, "Message 1 Sent")
                
            # Log to History
            try:
                import zynd_outreach_history
                zynd_outreach_history.log_outreach_event(username, "Abhinav", "Email", "Initial Pitch", f"Sent to: {prospect_email} | Subject: {subject}")
            except Exception:
                pass
            
            # Strict Jitter Delays (Live UI update so the user doesn't think the app broke)
            if emails_fired < max_emails:
                delay = random.randint(30, 75)
                if status_container: status_container.success(f"Email sent! Waiting {delay} seconds to bypass ISP spam filters...")
                time.sleep(delay)
                
        except Exception as e:
            return emails_fired, f"Socket Failure on lead {username}: {str(e)}"
            
    return emails_fired, "Campaign cycle successfully concluded."