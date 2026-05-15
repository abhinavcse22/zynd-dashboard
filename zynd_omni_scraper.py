import requests
import pandas as pd
from datetime import datetime
import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials

SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'

def scrape_discord_server(server_id, auth_token):
    """Rips member data from a Discord Server using an Auth Token."""
    headers = {"Authorization": auth_token}
    # Hits the member list endpoint (Note: results may be paginated in massive servers)
    url = f"https://discord.com/api/v9/guilds/{server_id}/members?limit=1000"
    
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return [], f"Discord Error: {response.status_code} - Token may be invalid or you lack permissions."
        
    members = response.json()
    leads = []
    today = datetime.now().strftime('%Y-%m-%d')
    
    for m in members:
        user = m.get('user', {})
        if user.get('bot'): continue
        
        leads.append([
            user.get('username', ''),
            f"Discord Server: {server_id}",
            user.get('global_name', ''),
            "No Bio (Discord)",
            today
        ])
    return leads, "Success"

def scrape_slack_workspace(auth_token):
    """Rips member data from a Slack workspace using a Bearer token."""
    headers = {"Authorization": f"Bearer {auth_token}"}
    url = "https://slack.com/api/users.list"
    
    response = requests.get(url, headers=headers)
    data = response.json()
    
    if not data.get("ok"):
        return [], f"Slack Error: {data.get('error')} - Check your token."
        
    leads = []
    today = datetime.now().strftime('%Y-%m-%d')
    
    for m in data.get('members', []):
        if m.get('is_bot') or m.get('deleted'): continue
        
        leads.append([
            m.get('name', ''),
            "Slack Workspace",
            m.get('profile', {}).get('real_name', ''),
            m.get('profile', {}).get('title', 'No Title'),
            today
        ])
    return leads, "Success"
