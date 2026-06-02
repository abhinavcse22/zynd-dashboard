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
import re
import math

# --- CONFIGURATION ---
SHEET_ID = '11rjC0aTk2xLc371tQT8sF2px8wObaeDX-eZQZrIq1-A'
KEYWORDS = ['agent', 'agents', 'ai-agent', 'ai agents', 'langchain', 'langgraph', 'crewai', 'autogen', 'openai', 'rag', 'mcp', 'n8n', 'workflow', 'automation', 'chatbot', 'llm', 'multi-agent', 'swarm', 'tool calling', 'function calling', 'vector db', 'embeddings', 'assistant', 'autonomous agent']

def get_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID).worksheet("github_stargazer_leads")

def make_request(url, headers, tokens):
    """Thread-safe API request that respects GitHub's strict Secondary Rate Limits."""
    retries = 3
    while retries > 0:
        current_token = random.choice(tokens)
        headers['Authorization'] = f'token {current_token}'
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:
            st.error("❌ GitHub Token Unauthorized! Check your st.secrets keys configuration.")
            return "AUTH_ERROR"
        elif response.status_code in [403, 429]:
            if 'retry-after' in response.headers:
                time.sleep(int(response.headers['retry-after']) + 1)
            else:
                time.sleep(2) 
            retries -= 1
        else:
            return None
    return None

def get_hidden_email(username, repos_data, headers, tokens):
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
    user = star['user']
    username = user['login']
    starred_at = star.get('starred_at', '')

    profile_url = f"https://api.github.com/users/{username}"
    profile_data = make_request(profile_url, headers_std, tokens)
    
    repos_url = f"https://api.github.com/users/{username}/repos?sort=updated&per_page=30"
    repos_data = make_request(repos_url, headers_std, tokens)

    score, bucket, action, kws, matched_repos, has_repo, activity_date = score_lead(profile_data or {}, repos_data or [], source_count)

    final_email = profile_data.get('email') if profile_data else ""
    if not final_email and repos_data and score >= 5:
        final_email = get_hidden_email(username, repos_data, headers_std, tokens)

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

    if profile_data and isinstance(profile_data, dict):
        lead_dict.update({
            'bio': profile_data.get('bio', ''), 'location': profile_data.get('location', ''),
            'company': profile_data.get('company', ''), 'public_email': final_email, 
            'website': profile_data.get('blog', ''), 'twitter_or_x': profile_data.get('twitter_username', ''),
            'public_repos_count': profile_data.get('public_repos', 0), 'followers_count': profile_data.get('followers', 0)
        })

    return lead_dict

def run_stargazer_radar(target_repos, max_repos, max_stargazers, min_score, dry_run=False):
    # --- 🪓 ANTI-STRING BUG PASS ---
    tokens = st.secrets["github"]["tokens"]
    if isinstance(tokens, str):
        tokens = [tokens] # Wraps single string secret into an iterable array
        
    sheet = get_sheet()
    
    # Deduplication extraction
    raw_data = sheet.get_all_values()
    seen_usernames = set()
    if len(raw_data) > 0:
        try:
            user_idx = raw_data[0].index('github_username')
            seen_usernames = {str(row[user_idx]).strip() for row in raw_data[1:] if len(row) > user_idx}
        except ValueError:
            pass 

    headers_star = {'Accept': 'application/vnd.github.v3.star+json'}
    headers_std = {'Accept': 'application/vnd.github.v3+json'}

    tasks_to_run = []
    
    for repo in target_repos[:max_repos]:
        st.info(f"🔍 Analyzing repository structure for: `{repo}`...")
        
        repo_info_url = f"https://api.github.com/repos/{repo}"
        repo_info = make_request(repo_info_url, headers_std, tokens)
        
        if repo_info == "AUTH_ERROR" or not repo_info:
            st.error(f"❌ Aborting. Could not establish communication with GitHub API endpoint.")
            continue
            
        total_stars = repo_info.get('stargazers_count', 0)
        st.write(f"📊 Meta-analysis: Repo has `{total_stars:,}` total stargazers.")
        
        if total_stars == 0:
            continue

        # Capping page parameters
        max_allowed_stars = min(total_stars, 40000) 
        last_page = math.ceil(max_allowed_stars / 100)
        
        st.write(f"⏭️ Route planning: Direct extraction on **Page {last_page}**...")
        
        url_last = f"https://api.github.com/repos/{repo}/stargazers?per_page=100&page={last_page}"
        stargazers = make_request(url_last, headers_star, tokens)
        
        if not stargazers or not isinstance(stargazers, list):
            st.warning("⚠️ GitHub served an empty block for this pagination index. Trying page minus 1...")
            if last_page > 1:
                url_last = f"https://api.github.com/repos/{repo}/stargazers?per_page=100&page={last_page - 1}"
                stargazers = make_request(url_last, headers_star, tokens)

        if not stargazers or not isinstance(stargazers, list):
            st.error("❌ Failed to receive data payload back from GitHub cluster node.")
            continue

        stargazers.reverse()
        st.write(f"📥 Received `{len(stargazers)}` potential raw nodes. Commencing date isolation filter...")

        skipped_by_date = 0
        skipped_by_dup = 0

        for star in stargazers[:max_stargazers]:
            # --- 6 MONTH STRICT FILTER ---
            starred_at = star.get('starred_at', '')
            if starred_at:
                dt = datetime.strptime(starred_at, "%Y-%m-%dT%H:%M:%SZ")
                days_ago = (datetime.now() - dt).days
                if days_ago > 180:
                    skipped_by_date += 1
                    continue 
            
            username = star['user']['login']
            if username in seen_usernames: 
                skipped_by_dup += 1
                continue 
                
            seen_usernames.add(username)
            tasks_to_run.append((star, repo, tokens, headers_std, 1))

        st.info(f"📊 Filter results: Dropped `{skipped_by_date}` stale histories, dropped `{skipped_by_dup}` duplicate keys.")

    final_data = []
    if tasks_to_run:
        st.info(f"🚀 Thread-mapping active on `{len(tasks_to_run)}` qualified nodes...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(process_single_stargazer, *task) for task in tasks_to_run]
            for future in concurrent.futures.as_completed(futures):
                try:
                    lead = future.result()
                    if lead['lead_score'] >= min_score:
                        final_data.append(lead)
                except Exception as e:
                    st.write(f"⚠️ Micro-thread execution error skipped a lead. Details: {e}")
                    pass
    else:
        st.warning("⚠️ Analysis complete, but 0 records cleared the initial gate.")

    if not dry_run and final_data:
        df_final = pd.DataFrame(final_data)
        cols = ['lead_id', 'github_username', 'github_profile_url', 'source_repo', 'starred_at', 'bio', 'location', 'company', 'public_email', 'website', 'twitter_or_x', 'linkedin', 'public_repos_count', 'followers_count', 'recent_activity_date', 'matched_keywords', 'matched_repos', 'has_ai_agent_repo', 'lead_score', 'lead_bucket', 'suggested_outreach_action', 'outreach_status', 'reply_status', 'agent_registered', 'registered_agent_url', 'notes', 'created_at', 'updated_at']
        
        for col in cols:
            if col not in df_final.columns: df_final[col] = ''
                
        df_final = df_final[cols].fillna("")
        sheet.append_rows(df_final.values.tolist()) 
        return len(df_final)
    
    return len(final_data) if dry_run else 0
