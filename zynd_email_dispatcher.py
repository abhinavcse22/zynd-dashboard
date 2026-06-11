import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import re
import requests
import time
import random
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import streamlit as st

# ==========================================
# 🛡️ THE INBOX ROTATION VAULT
# ==========================================
# Add your Gmail App Passwords here for now. 
# You can add as many accounts as you want; the system will rotate through them evenly.
SENDER_ACCOUNTS = [
    {"email": "your_email@gmail.com", "password": "your-app-password", "host": "smtp.gmail.com", "port": 587},
    # {"email": "hello@yourdomain.com", "password": "sendpilot-password", "host": "smtp.sendpilot.io", "port": 587},
]

# Note: I removed the single smtp inputs from the function arguments since the vault handles it now.
def run_cloud_email_campaign(mode, custom_subj, custom_msg, email_cap, progress_bar, status_text):
    # 1. Connect to DB
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key('11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A').worksheet("github_stargazer_leads")
    
    records = sheet.get_all_records()
    headers = sheet.row_values(1)
    status_col_idx = headers.index("outreach_status") + 1 if "outreach_status" in headers else None

    emails_fired = 0
    account_index = 0  # 🔄 Tracks which inbox is currently sending

    for idx, row in enumerate(records):
        if emails_fired >= email_cap: break
            
        prospect_email = str(row.get("public_email", "")).strip()
        status = str(row.get("outreach_status", "Pending")).strip()
        username = str(row.get("github_username", "Developer")).strip()
        bio = str(row.get("bio", "")).strip()
        signal = str(row.get("source_repo", "GitHub")).strip()
        
        if not prospect_email or "@" not in prospect_email or "noreply" in prospect_email.lower(): continue
        if status in ["Message 1 Sent", "DO NOT CONTACT 🛑", "Replied - Interested"]: continue
            
        status_text.write(f"Drafting highly-targeted email for {username}...")
        
        # 2. Generate Draft
        if mode == "✍️ Custom Template":
            subject = custom_subj.replace("{name}", username).replace("{repo}", signal).replace("{bio}", bio)
            body = custom_msg.replace("{name}", username).replace("{repo}", signal).replace("{bio}", bio)
        else:
            # The B2B SaaS Logic
            prompt = f"""
            You are Abhinav, a technical founder building Zynd (an OS and discovery network for AI agents).
            Write a highly effective, professional cold email to a developer named {username}.
            They recently interacted with this GitHub repository: {signal}.
            Their bio context: {bio}
            
            Structure the email using this exact B2B sales framework:
            1. The Hook: Acknowledge their interaction with {signal}. Transition smoothly into a relevant technical challenge they might face.
            2. The Value: Introduce Zynd. State clearly how it solves that challenge or helps builders like them.
            3. The Call to Action (CTA): A low-friction ask. (e.g., "Open to a 15-min chat next week?")
            
            STRICT RULES:
            - Sound like an elite technical founder. Professional, intelligent, but conversational.
            - DO NOT use cheesy marketing words ("synergies", "revolutionary", "delve").
            - Keep it under 4 short paragraphs.
            - Sign off as "Best,\nAbhinav". Do NOT use placeholders like [Your Name].
            - Subject line should read like a quick idea (e.g., "Quick idea regarding [repo]" or "[Name], a faster way to...").

            Format EXACTLY like this:
            SUBJECT: [your subject line]
            BODY: [your email body]
            """
            
            api_key = st.secrets["openrouter"]["api_key"]
            resp = requests.post("https://openrouter.ai/api/v1/chat/completions", 
                                 headers={"Authorization": f"Bearer {api_key}"}, 
                                 json={"model": "openai/gpt-4o-mini", "temperature": 0.4, "messages": [{"role": "user", "content": prompt}]})
                                 
            ai_text = resp.json()['choices'][0]['message']['content'].replace("**", "")
            
            subj_match = re.search(r'(?i)SUBJECT:\s*([^\n]+)', ai_text)
            body_match = re.search(r'(?i)BODY:\s*(.*)', ai_text, re.DOTALL)
            subject = subj_match.group(1).strip() if subj_match else f"Quick idea regarding {signal}"
            body = body_match.group(1).strip() if body_match else f"Hi {username},\n\nI noticed you were checking out {signal}. It got me thinking about how you are handling agent discovery right now.\n\nAt Zynd, we're building an OS that helps developers deploy and monetize their agents faster. I'd love to share the approach with you.\n\nOpen to a 15-min chat next week?\n\nBest,\nAbhinav"

        # 3. Fire SMTP with Inbox Rotation
        current_sender = SENDER_ACCOUNTS[account_index % len(SENDER_ACCOUNTS)]
        smtp_user = current_sender["email"]
        smtp_pass = current_sender["password"]
        smtp_host = current_sender["host"]
        smtp_port = current_sender["port"]

        try:
            msg = MIMEMultipart()
            msg['From'] = smtp_user
            msg['To'] = prospect_email
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))
            
            server = smtplib.SMTP(smtp_host, smtp_port)
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_user, prospect_email, msg.as_string())
            server.quit()
            
            emails_fired += 1
            account_index += 1 # 🔄 Move to the next inbox for the next email
            
            progress_bar.progress(int((emails_fired / email_cap) * 100))
            if status_col_idx: sheet.update_cell(idx + 2, status_col_idx, "Message 1 Sent")
            
            if emails_fired < email_cap:
                # 🛡️ THE JITTER UPGRADE: Exact 10s intervals trigger spam traps.
                delay = random.randint(15, 35)
                status_text.write(f"✅ Sent to {prospect_email} via {smtp_user}. Sleeping {delay}s to evade spam filters...")
                time.sleep(delay)
                
        except Exception as e:
            st.error(f"Failed to send to {prospect_email} via {smtp_user}: {e}")

    status_text.success(f"🏁 Campaign Complete! {emails_fired} emails sent successfully across {len(SENDER_ACCOUNTS)} inboxes.")