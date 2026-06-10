from fastapi import FastAPI, BackgroundTasks
from pydantic import BaseModel
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = FastAPI()

# 1. Define the incoming payload structure
class CampaignRequest(BaseModel):
    user_id: str
    target_segment: str
    max_emails: int
    # In production, we fetch these from Supabase using user_id, 
    # but for testing, the UI can pass them directly:
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_pass: str

# 2. The Heavy Background Worker (No UI Freezing!)
def execute_email_campaign(req: CampaignRequest):
    print(f"🚀 [BACKGROUND TASK] Starting campaign for user {req.user_id}...")
    
    # Example loop: Fetch leads from Supabase here, then iterate:
    for i in range(req.max_emails):
        print(f"📧 Sending email {i+1} of {req.max_emails}...")
        
        # simulated send logic...
        # server = smtplib.SMTP(req.smtp_host, req.smtp_port)
        # server.starttls()
        # server.login(req.smtp_user, req.smtp_pass)
        # ... send email ...
        # server.quit()
        
        # Human emulation delay (doesn't freeze the UI because it's in the background!)
        time.sleep(10) 
        
    print("✅ [BACKGROUND TASK] Campaign Complete!")

# 3. The API Endpoint
@app.post("/api/start-campaign")
async def start_campaign(req: CampaignRequest, background_tasks: BackgroundTasks):
    # Instantly hand the heavy lifting to the background task
    background_tasks.add_task(execute_email_campaign, req)
    
    # Return success to Streamlit in 0.1 seconds
    return {"status": "success", "message": "Campaign queued and running in the background!"}