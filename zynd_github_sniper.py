import requests
import time
import streamlit as st

# Pull the GitHub token securely from Streamlit Cloud secrets
GITHUB_TOKEN = st.secrets["github"]["token"]
HEADERS = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}

def extract_hidden_email(username):
    """The OSINT trick: Digs into public events to find hidden commit emails."""
    url = f"https://api.github.com/users/{username}/events/public"
    response = requests.get(url, headers=HEADERS)
    
    if response.status_code == 200:
        events = response.json()
        for event in events:
            if event['type'] == 'PushEvent':
                commits = event.get('payload', {}).get('commits', [])
                for commit in commits:
                    author_email = commit.get('author', {}).get('email', '')
                    if author_email and "noreply.github.com" not in author_email:
                        return author_email
    return "No public commit email"

def run_fork_sniper(target_repo, max_results=20):
    """Finds devs who forked a repo and extracts their data."""
    url = f"https://api.github.com/repos/{target_repo}/forks?sort=newest&per_page={max_results}"
    response = requests.get(url, headers=HEADERS)
    
    if response.status_code != 200:
        raise Exception(f"GitHub API Error: {response.text}")
        
    forks = response.json()
    sniped_leads = []
    
    for fork in forks:
        owner = fork['owner']
        username = owner['login']
        profile_url = owner['html_url']
        
        # Pull extra profile data
        user_response = requests.get(f"https://api.github.com/users/{username}", headers=HEADERS).json()
        name = user_response.get('name', username)
        bio = user_response.get('bio', '')
        twitter = user_response.get('twitter_username', '')
        
        # Run the OSINT email extractor
        email = user_response.get('email') 
        if not email:
            email = extract_hidden_email(username)
            
        time.sleep(0.5) # Prevent rate limiting
        
        sniped_leads.append({
            "Username": username,
            "Name": name,
            "Profile": profile_url,
            "Email": email,
            "Twitter": f"https://x.com/{twitter}" if twitter else "None",
            "Bio": str(bio).replace('\n', ' '),
            "Intent Source": f"Forked {target_repo}"
        })
        
    return sniped_leads
