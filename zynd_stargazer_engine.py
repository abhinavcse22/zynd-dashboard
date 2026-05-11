import requests
import time
from datetime import datetime
import gspread
import streamlit as st
import pandas as pd
from oauth2client.service_account import ServiceAccountCredentials
import uuid
import concurrent.futures
import random

# --- CONFIGURATION ---
SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'
KEYWORDS = ['agent', 'agents', 'ai-agent', 'ai agents', 'langchain', 'langgraph', 'crewai', 'autogen', 'openai', 'rag', 'mcp', 'n8n', 'workflow', 'automation', 'chatbot', 'llm', 'multi-agent', 'swarm', 'tool calling', 'function calling', 'vector db', 'embeddings', 'assistant', 'autonomous agent']

def get_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID).worksheet("github_stargazer_leads")

def make_request(url, headers, tokens):
    """Thread-safe API request with stateless random token rotation."""
    retries = 3
    while retries > 0:
        current_token = random.choice(tokens)
        headers['Authorization'] = f'token {current_token}'
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code in [403, 429]:
            time.sleep(1) # Back off if rate limited
            retries -= 1
        else:
            return None
    return None

def get_hidden_email(username, repos_data, headers, tokens):
    """OSINT Function: Hacks commit logs to find private email addresses."""
    for repo in repos_data[:3]: 
        repo_name = repo.get('name')
        commits_url = f"https://api.github.com/repos/{username}/{repo_name}/commits?author={username}&per_page=1"
        commits_data = make_request(commits_url, headers, tokens)
        
        if commits_data and isinstance(commits_data, list) and len(commits_data) > 0:
            try:
                email = commits_data[0]['commit']['author']['email']
                if email and 'noreply' not in email.lower() and '@' in email:
                    return email
            except: pass
    return ""

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
    elif bucket == "Warm lead": action = "Personalized email or social DM"
    elif bucket == "Nurture": action = "Invite to build session/community"
    else: action = "Skip for now"

    return score, bucket, action, list(matched_keywords), matched_repos, has_ai_agent_repo, recent_activity_date

def process_single_stargazer(star, repo, tokens, headers_std, source_count):
    """The individual task run by the thread pool."""
    user = star['user']
    username = user['login']
    starred_at = star.get('starred_at', '')

    # 1. Fetch Profile and Repos
    profile_url = f"https://api.github.com/users/{username}"
    profile_data = make_request(profile_url, headers_std, tokens)
    
    repos_url = f"https://api.github.com/users/{username}/repos?sort=updated&per_page=30"
    repos_data = make_request(repos_url, headers_std, tokens)

    # 2. Score the lead BEFORE doing the heavy email hack
    score, bucket, action, kws, matched_repos, has_repo, activity_date = score_lead(profile_data or {}, repos_data or [], source_count)

    # 3. CONDITIONAL OSINT: Only hack commits if it's a good lead
    final_email = profile_data.get('email') if profile_data else ""
    if not final_email and repos_data and score >= 5:
        final_email = get_hidden_email(username, repos_data, headers_std, tokens)
        if final_email: print(f"🔓 OSINT Unlocked hidden email for high-value lead: {username}")

    # 4. Compile the final dictionary
    lead_dict = {
        'lead_id': str(uuid.uuid4())[:8], 'github_username': username,
        'github_profile_url': user['html_url'], 'source_repo': repo,
        'starred_at': starred_at, 'outreach_status': 'Pending',
        'reply_status': 'None', 'agent_registered': 'No',
        'registered_agent_url': '', 'notes': '',
        'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'recent_activity_date': activity_date, 'matched_keywords': ', '.join(kws),
        'matched_repos': ', '.join(matched_repos), 'has_ai_agent_repo': has_repo,
        'lead_score': score, 'lead_bucket': bucket,
        'suggested_outreach_action': action, 'updated_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    if profile_data:
        lead_dict.update({
            'bio': profile_data.get('bio', ''), 'location': profile_data.get('location', ''),
            'company': profile_data.get('company', ''), 'public_email': final_email, 
            'website': profile_data.get('blog', ''), 'twitter_or_x': profile_data.get('twitter_username', ''),
            'public_repos_count': profile_data.get('public_repos', 0), 'followers_count': profile_data.get('followers', 0)
        })

    return lead_dict

def run_stargazer_radar(target_repos, max_repos, max_stargazers, min_score, dry_run=False):
    tokens = st.secrets["github"]["tokens"]
    sheet = get_sheet()
    
    # Track existing to prevent duplicates
    existing_records = sheet.get_all_records()
    seen_usernames = {str(row.get('github_username', '')) for row in existing_records}

    headers_star = {'Accept': 'application/vnd.github.v3.star+json'}
    headers_std = {'Accept': 'application/vnd.github.v3+json'}

    tasks_to_run = []
    
    # Stage 1: Fast Collection of Stargazer Usernames
    for repo in target_repos[:max_repos]:
        url = f"https://api.github.com/repos/{repo}/stargazers?per_page=100"
        stargazers = make_request(url, headers_star, tokens)
        
        if not stargazers: continue

        for star in stargazers[:max_stargazers]:
            username = star['user']['login']
            if username in seen_usernames: continue # Skip if we already have them
            seen_usernames.add(username)
            tasks_to_run.append((star, repo, tokens, headers_std, 1))

    # Stage 2: Multithreaded Processing (The 10x Speedup)
    final_data = []
    print(f"🚀 Launching Turbo Threads for {len(tasks_to_run)} leads...")
    
    # Process 10 users at the exact same time
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(process_single_stargazer, *task) for task in tasks_to_run]
        for future in concurrent.futures.as_completed(futures):
            try:
                lead = future.result()
                if lead['lead_score'] >= min_score:
                    final_data.append(lead)
            except Exception as e:
                pass

    # Stage 3: Push to Cloud
    if not dry_run and final_data:
        df_final = pd.DataFrame(final_data)
        cols = ['lead_id', 'github_username', 'github_profile_url', 'source_repo', 'starred_at', 'bio', 'location', 'company', 'public_email', 'website', 'twitter_or_x', 'linkedin', 'public_repos_count', 'followers_count', 'recent_activity_date', 'matched_keywords', 'matched_repos', 'has_ai_agent_repo', 'lead_score', 'lead_bucket', 'suggested_outreach_action', 'outreach_status', 'reply_status', 'agent_registered', 'registered_agent_url', 'notes', 'created_at', 'updated_at']
        
        for col in cols:
            if col not in df_final.columns: df_final[col] = ''
                
        df_final = df_final[cols].fillna("")
        sheet.append_rows(df_final.values.tolist()) # Use append_rows instead of clear() to keep history
        return len(df_final)
    
    return len(final_data) if dry_run else 0
