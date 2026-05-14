import pandas as pd
from googleapiclient.discovery import build
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Configuration
YOUTUBE_API_KEY = st.secrets["youtube"]["api_key"]
SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A' # Your master sheet ID

def hunt_micro_influencers(search_query, max_results=25):
    """Scans YouTube for coding tutorials and extracts micro-influencer channels."""
    youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
    
    # Step 1: Search for recent videos matching the technical niche
    search_response = youtube.search().list(
        q=search_query,
        part='snippet',
        type='video',
        order='relevance',
        maxResults=max_results
    ).execute()

    channel_ids = [item['snippet']['channelId'] for item in search_response.get('items', [])]

    if not channel_ids:
        return [], 0

    # Step 2: Extract deeper Channel Stats
    # We query the API again to get the exact subscriber counts
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
        
        # Basic parsing to see if they dropped a contact method in their bio
        contact = "Check About Page"
        if "@" in desc: contact = "Email hidden in bio"
        if "twitter.com" in desc.lower() or "x.com" in desc.lower(): contact = "Twitter Linked"

        channel_link = f"https://youtube.com/{custom_url}" if custom_url else f"https://youtube.com/channel/{channel['id']}"

        influencers.append([title, channel_link, subs, views, search_query, contact])

    # Step 3: THE GOLDILOCKS FILTER (Micro-Influencers Only)
    # We filter out anyone under 500 subs (too small) or over 100k subs (too expensive)
    micro_influencers = [inf for inf in influencers if 500 <= inf[2] <= 100000]

    if not micro_influencers:
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
