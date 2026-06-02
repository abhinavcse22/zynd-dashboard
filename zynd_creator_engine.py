import pandas as pd
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timezone, timedelta
import re

# Configuration
YOUTUBE_API_KEY = st.secrets["youtube"]["api_key"]
SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A' 

def hunt_micro_influencers(search_query, max_results=25):
    """Scans YouTube for active coding tutorials and extracts micro-influencer channels."""
    
    try:
        youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
        
        # 🛑 TTL WALL: Calculate exactly 180 days ago in RFC 3339 format (Required by YouTube)
        cutoff_date = (datetime.now(timezone.utc) - timedelta(days=180)).isoformat()
        
        # Step 1: Search for RECENT videos matching the technical niche
        with st.spinner(f"Querying YouTube for active creators uploading '{search_query}'..."):
            search_response = youtube.search().list(
                q=search_query,
                part='snippet',
                type='video',
                order='relevance',
                publishedAfter=cutoff_date, # 🛑 Strict TTL Enforcement injected into the API!
                maxResults=max_results
            ).execute()

        channel_ids = [item['snippet']['channelId'] for item in search_response.get('items', [])]

        if not channel_ids:
            return [], 0

        # Step 2: Extract deeper Channel Stats
        channels_response = youtube.channels().list(
            part='snippet,statistics',
            id=','.join(set(channel_ids))
        ).execute()

        influencers = []
        for channel in channels_response.get('items', []):
            title = channel['snippet']['title']
            subs = int(channel['statistics'].get('subscriberCount', 0))
            views = int(channel['statistics'].get('viewCount', 0))
            custom_url = channel['snippet'].get('customUrl', '')
            desc = channel['snippet'].get('description', '')
            
            # 🕵️‍♂️ Advanced Contact OSINT Parsing
            contact = "None Found"
            
            # Check for emails using regex
            email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', desc)
            if email_match:
                contact = f"Email: {email_match.group(0)}"
            elif "twitter.com" in desc.lower() or "x.com" in desc.lower():
                contact = "Twitter Linked in Bio"
            elif "linkedin.com" in desc.lower():
                contact = "LinkedIn Linked in Bio"

            channel_link = f"https://youtube.com/{custom_url}" if custom_url else f"https://youtube.com/channel/{channel['id']}"

            influencers.append([title, channel_link, subs, views, search_query, contact])

        # Step 3: THE GOLDILOCKS FILTER (Micro-Influencers Only)
        # 500 to 100k subs. Anything else is filtered out.
        micro_influencers = [inf for inf in influencers if 500 <= inf[2] <= 100000]

        if not micro_influencers:
            st.warning(f"Found channels, but none matched the 500-100k subscriber criteria.")
            return [], 0

        # Step 4: PUSH TO GOOGLE SHEETS
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
        gclient = gspread.authorize(creds)
        sheet = gclient.open_by_key(SHEET_ID).worksheet("Influencer Leads")

        existing_urls = set(sheet.col_values(2)[1:]) if len(sheet.get_all_values()) > 1 else set()
        new_rows = [row for row in micro_influencers if row[1] not in existing_urls]
        
        if new_rows:
            sheet.append_rows(new_rows)

        display_data = [{"Channel": r[0], "Subs": f"{r[2]:,}", "URL": r[1], "Contact": r[5]} for r in new_rows]
        return display_data, len(new_rows)

    except HttpError as e:
        if e.resp.status == 403 and "quotaExceeded" in str(e):
            st.error("🚨 YouTube API Quota Exceeded for today. Limit resets at midnight Pacific Time.")
        else:
            st.error(f"YouTube API Error: {e.resp.status} - {e._get_reason()}")
        return [], 0
    except Exception as e:
        st.error(f"System Error: {str(e)}")
        return [], 0
