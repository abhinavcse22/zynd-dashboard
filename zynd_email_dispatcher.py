import streamlit as st
import gspread
import requests
import smtplib
import time
import random
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from oauth2client.service_account import ServiceAccountCredentials

# --- ENVIRONMENT PARAMETERS ---
SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

def generate_personalized_payload(prospect_name, context_signal, bio):
    """Generates a high-conversion, value-first technical email."""
    OPENROUTER_API_KEY = st.secrets["openrouter"]["api_key"]
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # THE "TECHNICAL PEER" FORMULA
    prompt = f"""
    You are Abhinav, a fellow developer and founder of Zynd (a workspace for AI agent orchestration).
    
    Lead Name: {prospect_name}
    Signal: {context_signal}
    Bio/Context: {bio}
    
    DRAFT A COLD EMAIL USING THIS EXACT FORMULA:
    1. SUBJECT: [3-4 words, lowercase, specific to their repo/signal]
    2. BODY:
       hey {prospect_name},
       
       [1 observation about their specific tech stack/work on {context_signal}]
       
       [1 technical insight about how you solved a similar problem at Zynd]
       
       [The Ask: A specific, low-friction technical question, NOT a meeting request]
       
       cheers,
       abhinav
    
    STRICT RULES:
    - ALL LOWERCASE. No capital letters.
    - NO MARKETING FLUFF. Banned words: "seamless", "experience", "leverage", "platform", "comprehensive".
    - DO NOT ask for a call, a demo, or a "quick chat".
    - The CTA must be a question about their code or build process (e.g., "what are you using for your llm routing right now?").
    - MAX 50 WORDS.
    """
    
    data = {
        "model": "anthropic/claude-3-haiku", # Claude-3-Haiku is significantly more human/casual than GPT
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3
    }
    
    try:
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data, timeout=20)
        ai_text = response.json()['choices'][0]['message']['content'].strip()
        
        # Robust parsing
        subject_match = re.search(r'(?i)SUBJECT:\s*([^\n]+)', ai_text)
        body_match = re.search(r'(?i)BODY:\s*(.*)', ai_text, re.DOTALL)
        
        if subject_match and body_match:
            return subject_match.group(1).strip(), body_match.group(1).strip(), None
        return None, None, "AI format error"
    except Exception as e:
        return None, None, str(e)

def dispatch_campaign(max_emails=10, mode="AI Generated", custom_subject="", custom_body="", status_container=None):
    """Scans databases, applies chosen template/AI, fires via SMTP, and logs updates safely."""
    if "smtp" not in st.secrets:
        return 0, "Error: [smtp] secrets block is missing."

    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    
    try:
        sheet = client.open_by_key(SHEET_ID).worksheet("github_stargazer_leads")
        records = sheet.get_all_records()
        
        headers = sheet.row_values(1)
        if "outreach_status" in headers:
            status_col_idx = headers.index("outreach_status") + 1
        else:
            status_col_idx = None
            
    except Exception as e:
        return 0, f"Database Connection Error: {str(e)}"
    
    if not records:
        return 0, "No leads located inside the target database."

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
        
        if not prospect_email or "@" not in prospect_email or "noreply" in prospect_email.lower():
            continue
        if status in ["Message 1 Sent", "DO NOT CONTACT 🛑", "Replied - Interested", "AI Generation Failed"]:
            continue
            
        if mode == "✍️ Custom Template":
            if status_container:
                status_container.info(f"Applying custom template for {username}...")
            subject = custom_subject.replace("{name}", username).replace("{repo}", signal).replace("{bio}", bio)
            body = custom_body.replace("{name}", username).replace("{repo}", signal).replace("{bio}", bio)
        else:
            if status_container:
                status_container.info(f"Drafting AI payload for {username}...")
                
            subject, body, error_msg = generate_personalized_payload(username, signal, bio)
            
            if not subject or not body:
                if status_container:
                    # NOW IT TELLS YOU EXACTLY WHY IT FAILED
                    status_container.error(f"Failed on {username} | {error_msg}")
                    
                if status_col_idx:
                    try:
                        sheet.update_cell(idx + 2, status_col_idx, "AI Generation Failed")
                        time.sleep(2) 
                    except Exception:
                        pass
                continue
        
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = prospect_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        try:
            if status_container:
                status_container.warning(f"Connecting to SMTP server... firing email to {prospect_email}")
            
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, prospect_email, msg.as_string())
            server.quit()
            
            emails_fired += 1
            
            if status_col_idx:
                sheet.update_cell(idx + 2, status_col_idx, "Message 1 Sent")
                
            try:
                import zynd_outreach_history
                zynd_outreach_history.log_outreach_event(username, "Abhinav", "Email", "Initial Pitch", f"Sent to: {prospect_email} | Subject: {subject}")
            except Exception:
                pass
            
            if emails_fired < max_emails:
                delay = random.randint(120, 300) 
                if status_container:
                    status_container.success(f"Email sent! Human emulation active: Sleeping for {delay} seconds to bypass ISP spam filters...")
                time.sleep(delay)
                
        except Exception as e:
            return emails_fired, f"Socket Failure on lead {username}: {str(e)}"
            
    return emails_fired, "Campaign cycle successfully concluded."