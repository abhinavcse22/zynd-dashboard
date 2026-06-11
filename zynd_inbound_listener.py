import imaplib
import email
from email.header import decode_header
import email.utils
import requests
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import streamlit as st

CRM_TABS = ["github_stargazer_leads"]

def classify_intent(subject, body):
    prompt = f"""
    You are an AI sales assistant managing a CRM for an AI Agent OS (Zynd).
    Read the following email reply from a developer.
    
    Subject: {subject}
    Body: {body}
    
    Classify the intent into EXACTLY ONE of these categories. Return ONLY the category name.
    
    Categories:
    1. "Replied - Interested" (They want to chat, asked for docs, or showed positive interest)
    2. "Replied - Not Interested" (They said no, unsubscribe, or take me off your list)
    3. "Replied - Question" (They asked a technical question but didn't say yes or no)
    4. "Bounce" (Automated delivery failure)
    5. "Out of Office" (Automated OOO reply)
    """
    
    api_key = st.secrets["openrouter"]["api_key"]
    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions", 
            headers={"Authorization": f"Bearer {api_key}"}, 
            json={"model": "openai/gpt-4o-mini", "temperature": 0.0, "messages": [{"role": "user", "content": prompt}]}
        )
        classification = resp.json()['choices'][0]['message']['content'].strip().replace('"', '').replace('**', '')
        
        valid_statuses = ["Replied - Interested", "Replied - Not Interested", "Replied - Question", "Bounce", "Out of Office"]
        if classification in valid_statuses:
            return classification
        return "Replied - Unclassified"
    except Exception as e:
        return "Replied - Unclassified"

def update_crm_status(client, sender_email, new_status, status_text):
    for tab in CRM_TABS:
        try:
            sheet = client.open_by_key('11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A').worksheet(tab)
            records = sheet.get_all_records()
            headers = sheet.row_values(1)
            
            email_col_name = next((h for h in headers if "email" in h.lower()), None)
            status_col_name = next((h for h in headers if "status" in h.lower()), None)
            
            if not email_col_name or not status_col_name:
                continue
                
            status_col_idx = headers.index(status_col_name) + 1
            
            for idx, row in enumerate(records):
                db_email = str(row.get(email_col_name, "")).strip().lower()
                if db_email == sender_email.lower():
                    current_status = str(row.get(status_col_name, ""))
                    if "Interested" not in current_status:
                        sheet.update_cell(idx + 2, status_col_idx, new_status)
                        status_text.success(f"✅ Updated {sender_email} to '{new_status}' in CRM.")
                    return True
        except Exception as e:
            pass
            
    return False

def run_cloud_inbound_sweep(imap_user, imap_pass, status_text):
    """Streamlit-compatible IMAP sweeper with Secure Whitelisting."""
    status_text.info(f"📥 Booting Inbound Sweep for {imap_user}...")
    
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    g_client = gspread.authorize(creds)
    
    # 🛡️ THE FIREWALL: Cache all valid leads first
    status_text.write("🗄️ Building secure whitelist from CRM to ignore non-lead emails...")
    known_emails = set()
    for tab in CRM_TABS:
        try:
            sheet = g_client.open_by_key('11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A').worksheet(tab)
            records = sheet.get_all_records()
            if records:
                headers = sheet.row_values(1)
                email_col = next((h for h in headers if "email" in h.lower()), None)
                if email_col:
                    for row in records:
                        val = str(row.get(email_col, "")).strip().lower()
                        if val: known_emails.add(val)
        except Exception:
            pass
            
    status_text.write(f"✅ Loaded {len(known_emails)} known leads into memory.")

    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        mail.login(imap_user, imap_pass)
        mail.select("inbox")
        
        status, messages = mail.search(None, "UNSEEN")
        email_ids = messages[0].split()
        
        if not email_ids:
            status_text.success("📭 Inbox zero! No new unread replies.")
            mail.logout()
            return
            
        status_text.write(f"📬 Found {len(email_ids)} unread messages. Filtering against CRM...")
        
        processed_count = 0
        
        for e_id in email_ids:
            # 🛡️ THE PEEK UPGRADE: Reads the email without marking it as "\Seen"
            res, msg_data = mail.fetch(e_id, "(BODY.PEEK[])")
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    
                    raw_from = msg.get("From", "")
                    sender_name, sender_email = email.utils.parseaddr(raw_from)
                    sender_email = sender_email.lower()
                    
                    # 🛑 IF NOT IN CRM, IGNORE IT COMPLETELY
                    if sender_email not in known_emails:
                        continue
                        
                    # 🎯 If we get here, it's a valid lead! Process it.
                    processed_count += 1
                    status_text.write(f"🎯 Target Acquired! AI classifying reply from: {sender_email}")
                    
                    subject, encoding = decode_header(msg.get("Subject", ""))[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(encoding if encoding else "utf-8")
                        
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                try:
                                    body = part.get_payload(decode=True).decode()
                                    break
                                except: pass
                    else:
                        body = msg.get_payload(decode=True).decode()
                        
                    intent = classify_intent(subject, body[:1000])
                    
                    update_crm_status(g_client, sender_email, intent, status_text)
                    
                    # Target processed successfully. Mark it as read.
                    mail.store(e_id, '+FLAGS', '\\Seen')
                    
        mail.logout()
        status_text.success(f"🏁 Sweep Complete. Processed {processed_count} valid lead replies. Ignored other emails.")
        
    except Exception as e:
        status_text.error(f"❌ IMAP Error: {e}")