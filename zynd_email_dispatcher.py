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
    """Hits OpenRouter to craft a high-converting, peer-to-peer cold email."""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    prompt = f"""
    Act as Abhinav, a technical founder building Zynd. Write a cold email to a developer.
    
    Lead Name: {prospect_name}
    Repo/Signal they interacted with: {context_signal}
    Their Bio: {bio}
    
    Guidelines for the email:
    1. Tone: Peer-to-peer, relaxed, engineer-to-engineer. Do NOT sound like a marketer. Use lowercase for casualness where appropriate.
    2. Length: 3-4 short paragraphs maximum. Highly readable.
    3. Content: 
       - Acknowledge their specific work or interaction with {context_signal}.
       - Briefly mention Zynd: "we're building a workspace for autonomous AI agents to get discovered and integrated."
       - Soft call to action: "Would love to get your eyes on it" or "Any interest in taking a quick look?"
    
    You MUST return the output in exactly this format with no other text:
    SUBJECT: [Your Subject Line]
    BODY: [Your Email Body]
    """
    
    data = {
        "model": "google/gemini-2.5-flash",
        "messages": [{"role": "user", "content": prompt}]
    }
    
    try:
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=data, timeout=20)
        if response.status_code == 200:
            ai_text = response.json()['choices'][0]['message']['content']
            if "SUBJECT:" in ai_text and "BODY:" in ai_text:
                subject = ai_text.split("SUBJECT:")[1].split("BODY:")[0].strip()
                body = ai_text.split("BODY:")[1].strip()
                return subject, body
        return None, None # Return None if AI fails so we don't send a garbage fallback
    except Exception:
        return None, None

def dispatch_campaign(max_emails=10, mode="AI Generated", custom_subject="", custom_body="", status_container=None):
    """Scans databases, applies chosen template/AI, fires via SMTP, and logs updates."""
    if "smtp" not in st.secrets:
        return 0, "Error: [smtp] secrets block is missing."

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
        if status in ["Message 1 Sent", "DO NOT CONTACT 🛑", "Replied - Interested", "AI Generation Failed"]:
            continue
            
        # --- MESSAGE GENERATION LOGIC ---
        if mode == "Custom Template":
            if status_container: status_container.info(f"Applying custom template for {username}...")
            # Inject variables into the user's template
            subject = custom_subject.replace("{name}", username).replace("{repo}", signal).replace("{bio}", bio)
            body = custom_body.replace("{name}", username).replace("{repo}", signal).replace("{bio}", bio)
        else:
            if status_container: status_container.info(f"Drafting AI payload for {username}...")
            subject, body = generate_personalized_payload(username, signal, bio)
            
            # If AI fails, skip this lead and mark it so we don't send a bad email
            if not subject or not body:
                if status_container: status_container.error(f"AI failed to generate quality email for {username}. Skipping to protect brand.")
                row_num = idx + 2
                headers = sheet.row_values(1)
                if "outreach_status" in headers:
                    sheet.update_cell(row_num, headers.index("outreach_status") + 1, "AI Generation Failed")
                continue
        
        # --- EMAIL DISPATCH ---
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
            
            # EXTREME STEALTH DELAY (2 to 5 minutes between emails to prevent account bans)
            if emails_fired < max_emails:
                delay = random.randint(120, 300) 
                if status_container: status_container.success(f"Email sent! Human emulation active: Sleeping for {delay} seconds to bypass ISP spam filters...")
                time.sleep(delay)
                
        except Exception as e:
            return emails_fired, f"Socket Failure on lead {username}: {str(e)}"
            
    return emails_fired, "Campaign cycle successfully concluded."