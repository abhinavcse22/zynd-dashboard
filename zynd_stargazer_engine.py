import requests
import time
from datetime import datetime
import gspread
import streamlit as st
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials
import uuid

# --- CONFIGURATION ---
SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'
KEYWORDS = ['agent', 'agents', 'ai-agent', 'ai agents', 'langchain', 'langgraph', 'crewai', 'autogen', 'openai', 'rag', 'mcp', 'n8n', 'workflow', 'automation', 'chatbot', 'llm', 'multi-agent', 'swarm', 'tool calling', 'function calling', 'vector db', 'embeddings', 'assistant', 'autonomous agent']

def get_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID).worksheet("github_stargazer_leads")

def make_request(url, headers, tokens, token_idx):
    """Handles API requests with token rotation and rate limit protection."""
    while True:
        current_token = tokens[token_idx % len(tokens)]
        headers['Authorization'] = f'token {current_token}'
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            return response.json(), token_idx
        elif response.status_code in [403, 429]:
            token_idx += 1
            time.sleep(2)
        else:
            return None, token_idx

def get_hidden_email(username, repos_data, headers, tokens, token_idx):
    """OSINT Function: Hacks commit logs to find private email addresses."""
    # Check top 3 recently updated repos to save API tokens
    for repo in repos_data[:3]: 
        repo_name = repo.get('name')
        commits_url = f"https://api.github.com/repos/{username}/{repo_name}/commits?author={username}&per_page=1"
        commits_data, token_idx = make_request(commits_url, headers, tokens, token_idx)
        
        if commits_data and isinstance(commits_data, list) and len(commits_data) > 0:
            try:
                email = commits_data[0]['commit']['author']['email']
                # Filter out Github's fake privacy emails
                if email and 'noreply' not in email.lower() and '@' in email:
                    return email, token_idx
            except:
                pass
    return "", token_idx

def score_lead(user_data, repos_data, target_repos_count):
    score = 0
    matched_keywords = set()
    matched_repos = []
    has_ai_agent_repo = "No"

    score += 1 if target_repos_count == 1 else 2

    for repo in repos_data:
        search_text = f"{repo.get('name', '')} {repo.get('description', '')} {' '.join(repo.get('topics', []))}".lower()
        found_kws = [kw for kw in KEYWORDS if kw in search_text]
        if found_kws:
            matched_keywords.update(found_kws)
            matched_repos.append(repo.get('name'))
            has_ai_agent_repo = "Yes"
    
    if has_ai_agent_repo == "Yes": score += 3

    updated_at = user_data.get('updated_at')
    recent_activity_date = ""
    if updated_at:
        dt = datetime.strptime(updated_at, "%Y-%m-%dT%H:%M:%SZ")
        recent_activity_date = dt.strftime("%Y-%m-%d")
        if (datetime.now() - dt).days <= 60: score += 2
        else: score -= 2
    else: score -= 2

    if user_data.get('email') or user_data.get('blog') or user_data.get('twitter_username'): score += 1
    elif not repos_data: score -= 2

    bio = (user_data.get('bio') or "").lower()
    if any(kw in bio for kw in ['ai', 'agent', 'automation', 'devtools', 'open source', 'startup']): score += 1

    score = max(0, min(score, 10))
    if score >= 8: bucket = "Hot lead"
    elif score >= 5: bucket = "Warm lead"
    elif score >= 3: bucket = "Nurture"
    else: bucket = "Low priority"

    if bucket == "Hot lead" and has_ai_agent_repo == "Yes": action = "Personalized GitHub issue/PR + email if public"
    elif bucket == "Warm lead" and (user_data.get('email') or user_data.get('twitter_username')): action = "Personalized email or social DM"
    elif bucket == "Nurture": action = "Invite to build session/community"
    else: action = "Skip for now"

    return score, bucket, action, list(matched_keywords), matched_repos, has_ai_agent_repo, recent_activity_date

def run_stargazer_radar(target_repos, max_repos, max_stargazers, min_score, dry_run=False):
    tokens = st.secrets["github"]["tokens"]
    token_idx = 0
    sheet = get_sheet()
    
    existing_records = sheet.get_all_records()
    df_existing = pd.DataFrame(existing_records) if existing_records else pd.DataFrame()
    
    user_dict = {}
    if not df_existing.empty:
        for _, row in df_existing.iterrows():
            user_dict[row['github_username']] = row.to_dict()

    processed_repos = 0
    headers_star = {'Accept': 'application/vnd.github.v3.star+json'}
    headers_std = {'Accept': 'application/vnd.github.v3+json'}

    for repo in target_repos[:max_repos]:
        url = f"https://api.github.com/repos/{repo}/stargazers?per_page=100"
        stargazers, token_idx = make_request(url, headers_star, tokens, token_idx)
        
        if not stargazers: continue

        for star in stargazers[:max_stargazers]:
            user = star['user']
            username = user['login']
            starred_at = star.get('starred_at', '')

            if username in user_dict:
                sources = str(user_dict[username].get('source_repo', '')).split(',')
                if repo not in sources:
                    sources.append(repo)
                    user_dict[username]['source_repo'] = ','.join(filter(None, sources))
            else:
                user_dict[username] = {
                    'lead_id': str(uuid.uuid4())[:8], 'github_username': username,
                    'github_profile_url': user['html_url'], 'source_repo': repo,
                    'starred_at': starred_at, 'outreach_status': 'Pending',
                    'reply_status': 'None', 'agent_registered': 'No',
                    'registered_agent_url': '', 'notes': '',
                    'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }

            profile_url = f"https://api.github.com/users/{username}"
            profile_data, token_idx = make_request(profile_url, headers_std, tokens, token_idx)
            
            repos_url = f"https://api.github.com/users/{username}/repos?sort=updated&per_page=30"
            repos_data, token_idx = make_request(repos_url, headers_std, tokens, token_idx)
            
            # --- THE MAGIC OSINT STEP ---
            # Try public email first. If none, deploy hidden commit log scraper.
            final_email = profile_data.get('email') if profile_data else ""
            if not final_email and repos_data:
                final_email, token_idx = get_hidden_email(username, repos_data, headers_std, tokens, token_idx)
                if final_email: print(f"🔓 OSINT Unlocked hidden email for {username}")

            if profile_data:
                user_dict[username].update({
                    'bio': profile_data.get('bio', ''), 'location': profile_data.get('location', ''),
                    'company': profile_data.get('company', ''), 
                    'public_email': final_email, # Now stores both public OR hidden emails
                    'website': profile_data.get('blog', ''), 'twitter_or_x': profile_data.get('twitter_username', ''),
                    'public_repos_count': profile_data.get('public_repos', 0), 'followers_count': profile_data.get('followers', 0)
                })
            
            source_count = len(user_dict[username]['source_repo'].split(','))
            score, bucket, action, kws, matched_repos, has_repo, activity_date = score_lead(profile_data or {}, repos_data or [], source_count)
            
            user_dict[username].update({
                'recent_activity_date': activity_date, 'matched_keywords': ', '.join(kws),
                'matched_repos': ', '.join(matched_repos), 'has_ai_agent_repo': has_repo,
                'lead_score': score, 'lead_bucket': bucket,
                'suggested_outreach_action': action, 'updated_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            time.sleep(0.5) # Safety delay
        processed_repos += 1

    final_data = [data for data in user_dict.values() if data['lead_score'] >= min_score]
    
    if not dry_run and final_data:
        df_final = pd.DataFrame(final_data)
        cols = ['lead_id', 'github_username', 'github_profile_url', 'source_repo', 'starred_at', 'bio', 'location', 'company', 'public_email', 'website', 'twitter_or_x', 'linkedin', 'public_repos_count', 'followers_count', 'recent_activity_date', 'matched_keywords', 'matched_repos', 'has_ai_agent_repo', 'lead_score', 'lead_bucket', 'suggested_outreach_action', 'outreach_status', 'reply_status', 'agent_registered', 'registered_agent_url', 'notes', 'created_at', 'updated_at']
        
        for col in cols:
            if col not in df_final.columns:
                df_final[col] = ''
                
        df_final = df_final[cols].fillna("")
        
        sheet.clear()
        sheet.update([df_final.columns.values.tolist()] + df_final.values.tolist())
        return len(df_final)
    
    return len(final_data) if dry_run else 0
