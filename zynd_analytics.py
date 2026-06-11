import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

@st.cache_data(ttl=300) # Caches the data for 5 minutes so the dashboard loads instantly
def load_crm_data():
    """Securely pulls the latest telemetry from the Data Lake."""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key('11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A').worksheet("github_stargazer_leads")
    return pd.DataFrame(sheet.get_all_records())

def render_pipeline_overview():
    st.markdown("## 📊 Global Pipeline Overview")
    st.write("Real-time telemetry of your acquisition and outreach engines.")

    with st.spinner("Pulling live telemetry from Data Lake..."):
        try:
            df = load_crm_data()
        except Exception as e:
            st.error(f"Failed to load database: {e}")
            return

    # Dynamically find the status column
    status_col = next((col for col in df.columns if "status" in col.lower()), None)
    if not status_col:
        st.warning("⚠️ Could not locate a status column in the database.")
        return

    # --- CRUNCHING THE METRICS ---
    total_leads = len(df)
    
    # Filter for valid emails to see our actual addressable market
    valid_emails = df[df['public_email'].astype(str).str.contains('@', na=False)]
    contactable = len(valid_emails)

    contacted = len(df[df[status_col].astype(str).str.contains("Sent|Replied", case=False, na=False)])
    replied = len(df[df[status_col].astype(str).str.contains("Replied", case=False, na=False)])
    interested = len(df[df[status_col].astype(str).str.contains("Interested", case=False, na=False)])

    # --- 1. TOP LEVEL HUD ---
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Extracted", f"{total_leads:,}")
    col2.metric("Total Contacted", f"{contacted:,}", f"{(contacted/contactable)*100:.1f}% of target" if contactable else "0%")
    col3.metric("Total Replies", f"{replied:,}", f"{(replied/max(contacted, 1))*100:.1f}% response rate")
    col4.metric("🔥 Interested", f"{interested:,}")

    st.divider()

    # --- 2. PRIORITY TARGETS TABLE ---
    st.markdown("### 🎯 Priority Targets (Hot Leads)")
    st.write("These developers replied positively. **Manual follow-up required.**")
    
    interested_df = df[df[status_col].astype(str) == "Replied - Interested"]

    if not interested_df.empty:
        # Clean up the table to only show what you need to close the deal
        display_cols = [c for c in ["github_username", "public_email", "source_repo", status_col] if c in interested_df.columns]
        st.dataframe(interested_df[display_cols], width=None, hide_index=True)
    else:
        st.info("📭 No interested replies yet. Keep firing the outbound engines!")

    st.divider()

    # --- 3. CAMPAIGN HEALTH CHART ---
    st.markdown("### 📈 Pipeline Distribution")
    
    # Group the statuses and plot them
    status_counts = df[status_col].replace("", "Pending").value_counts().reset_index()
    status_counts.columns = ['Status', 'Lead Count']
    
    st.bar_chart(data=status_counts, x='Status', y='Lead Count', color="#4A90E2")