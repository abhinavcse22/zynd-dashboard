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
# 🛡️ THE ENCRYPTED INBOX ROTATION VAULT
# ==========================================
def get_secure_sender_accounts():
    """Pulls the email credentials securely from Streamlit Secrets."""
    accounts = []
    if "smtp" in st.secrets:
        smtp_data = st.secrets["smtp"]
        
        # 🧠 THE FIX: Smart Detection
        # If "email" is directly inside [smtp], it's a single account.
        if "email" in smtp_data:
            accounts.append(dict(smtp_data))
        else:
            # Otherwise, they are using [smtp.account1], [smtp.account2], etc.
            for key in smtp_data:
                accounts.append(dict(smtp_data[key]))
                
    if not accounts:
        st.error("❌ Security Error: No SMTP accounts found in Streamlit Secrets under [smtp].")
        st.stop()
        
    return accounts

def run_cloud_email_campaign(mode, custom_subj, custom_msg, email_cap, progress_bar, status_text):
    # 1. Connect to DB
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key('11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A').worksheet("github_stargazer_leads")
    
    records = sheet.get_all_records()
    headers = sheet.row_values(1)
    status_col_idx = headers.index("outreach_status") + 1 if "outreach_status" in headers else None

    # 🛑 SECURITY FIX: Load the secure accounts from the vault dynamically
    SENDER_ACCOUNTS = get_secure_sender_accounts()

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
            # 🛑 THE FIX: We instruct the LLM to output pure JSON.
            prompt = f"""
            You are Abhinav, a technical founder building Zynd (an OS and discovery network for AI agents).
            Write a highly effective, professional cold email to a developer named {username}.
            They recently interacted with this GitHub repository: {signal}.
            Their bio context: {bio}
            
            Structure the email using this exact B2B sales framework:
            1. The Hook: Acknowledge their interaction with {signal}. 
            2. The Value: Introduce Zynd and how it helps them deploy/monetize faster.
            3. The CTA: A low-friction ask (e.g., "Open to a 15-min chat next week?").
            
            STRICT RULES:
            - Sound like an elite technical founder. Professional, intelligent, but conversational.
            - DO NOT use cheesy marketing words ("synergies", "revolutionary", "delve").
            - Keep it under 4 short paragraphs. Sign off as "Best,\nAbhinav".
            
            OUTPUT FORMAT:
            You must respond ONLY with a valid JSON object containing exactly two keys: "subject" and "body".
            Do not include markdown blocks, backticks, or conversational text.
            Example: {{"subject": "Quick idea regarding their repo", "body": "Hi name, \\n\\nBody text here."}}
            """
            
            api_key = st.secrets["openrouter"]["api_key"]
            try:
                # 🛑 THE FIX: We use 'response_format' to guarantee JSON schema if the model supports it
                resp = requests.post("https://openrouter.ai/api/v1/chat/completions", 
                                     headers={"Authorization": f"Bearer {api_key}"}, 
                                     json={
                                         "model": "openai/gpt-4o-mini", 
                                         "temperature": 0.3, 
                                         "response_format": {"type": "json_object"},
                                         "messages": [{"role": "user", "content": prompt}]
                                     }, timeout=15)
                                     
                ai_text = resp.json()['choices'][0]['message']['content'].strip()
                
                # Strip markdown code blocks just in case the LLM disobeys the pure JSON rule
                if ai_text.startswith("```json"):
                    ai_text = ai_text[7:-3].strip()
                elif ai_text.startswith("```"):
                    ai_text = ai_text[3:-3].strip()
                    
                import json
                email_data = json.loads(ai_text)
                
                subject = email_data.get("subject", f"Quick idea regarding {signal}")
                body = email_data.get("body", f"Hi {username},\n\nI noticed you were checking out {signal}...\n\nBest,\nAbhinav")
                
            except Exception as e:
                print(f"⚠️ AI Parsing Failed, using fallback. Error: {e}")
                subject = f"Quick idea regarding {signal}"
                body = f"Hi {username},\n\nI noticed you were checking out {signal}. It got me thinking about how you are handling agent discovery right now.\n\nAt Zynd, we're building an OS that helps developers deploy and monetize their agents faster. I'd love to share the approach with you.\n\nOpen to a 15-min chat next week?\n\nBest,\nAbhinav"

        # 3. Fire SMTP with Inbox Rotation
        current_sender = SENDER_ACCOUNTS[account_index % len(SENDER_ACCOUNTS)]
        
        # 🛑 THE FIX: Use .get() to provide safe defaults and prevent KeyErrors
        smtp_user = current_sender.get("email", "")
        smtp_pass = current_sender.get("password", "")
        smtp_host = current_sender.get("host", "smtp.gmail.com")  # Defaults to Gmail if missing
        smtp_port = current_sender.get("port", 587)               # Defaults to 587 if missing

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