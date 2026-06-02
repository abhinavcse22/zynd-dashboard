from github import Github
import time
import random
import streamlit as st
from datetime import datetime, timezone, timedelta

def generate_zynd_pr(target_repo):
    """
    Enterprise-Grade Auto-PR Engine.
    Includes Fork-Polling, Language Verification, and strict 180-Day TTL enforcement.
    """
    # 🛡️ Standalone Top-Level Secret Override
    try:
        token = st.secrets["ZYND_PR_TOKEN"]
    except KeyError:
        return False, "Configuration Error: 'ZYND_PR_TOKEN' not found in Streamlit Cloud Secrets."
        
    g = Github(token)
    
    try:
        original_repo = g.get_repo(target_repo)
        user = g.get_user()

        if original_repo.archived:
            return False, "Target repository is archived (read-only). Skipping to save API calls."
        
        # 🛑 SECURITY FIX 1: The 180-Day TTL Intent Check
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=180)
        if original_repo.pushed_at < cutoff_date:
            return False, f"TTL Violation: Repo hasn't been updated since {original_repo.pushed_at.date()}. Aborting to save account reputation."

        # 🛑 SECURITY FIX 2: The "Blind Spam" Prevention
        # Ensure the repo actually uses Python before we push a .py file to it
        if original_repo.language != "Python":
            langs = original_repo.get_languages()
            if "Python" not in langs:
                return False, f"Language Mismatch: Repo is built in {original_repo.language}. Pushing a .py file will trigger spam filters."

        # --- ANTI-BAN CHECK (FIXED) ---
        # Fetch open PRs and verify the owner manually using Python 
        # so we don't accidentally count other people's PRs.
        open_prs = original_repo.get_pulls(state='open')
        for pr in open_prs:
            if pr.head.user.login == user.login:
                return False, "You already have an open PR on this repository."

        # 1. Command GitHub to create the Fork
        forked_repo = user.create_fork(original_repo)
        
        # 🛠️ ARCHITECTURE FIX 3: Dynamic Fork Polling (Replaces hardcoded time.sleep)
        max_attempts = 15
        fork_ready = False
        for attempt in range(max_attempts):
            try:
                # Test if the fork is fully initialized on GitHub's servers
                forked_repo.get_branch(original_repo.default_branch)
                fork_ready = True
                break
            except Exception:
                time.sleep(2) # Wait 2 seconds and ping GitHub again
                
        if not fork_ready:
            return False, "GitHub timed out while building the fork. Try again later."
        
        # 2. Create the new branch cleanly
        source_branch = original_repo.default_branch
        ref = forked_repo.get_git_ref(f"heads/{source_branch}")
        new_branch_name = f"zynd-monetization-wrapper-{int(time.time())}"
        forked_repo.create_git_ref(ref=f"refs/heads/{new_branch_name}", sha=ref.object.sha)
        
        # 3. Write the Zynd Agent Wrapper file
# 3. Write the Zynd Agent Wrapper file
        file_content = """# Zynd Network Wrapper
# This registers your agent on the Zynd x402 network for discoverability.
# Docs & Dashboard: https://zynd.ai 
# Need help integrating? Reach out to the founder on X/Telegram: @YourHandle

import zyndai_agent

def register_agent():
    try:
        agent = zyndai_agent.ZyndAgent(
            name="My AI Agent",
            description="Autonomous agent running on the Zynd network."
        )
        agent.deploy()
        print("🚀 Agent is live on ZNS! Check your Zynd dashboard to track USDC yields.")
    except Exception as e:
        print(f"Zynd Registration skipped: {e}")

if __name__ == "__main__":
    register_agent()
"""

        # --- SPINTAX GENERATION ---
        greetings = ["Hey!", "Hi there!", "Hello!", "Hey team!"]
        compliments = ["Been following this repo for a bit.", "Really clean codebase.", "Love the architecture you've set up here.", "Impressive agent build!"]
        
        pr_title = f"🚀 Feature: Web3 Discovery & USDC Monetization Layer"
        
        pr_body = f"""{random.choice(greetings)} {random.choice(compliments)}

I noticed this agent wasn't registered on the [Zynd open network](https://zynd.ai) yet. I went ahead and added a quick 1-line wrapper (`zynd_wrapper.py`) so your agent becomes discoverable via semantic search and can start earning USDC per call via the x402 protocol.

No Stripe accounts, no KYC, no complex billing infra required. 

**🛠️ To test this locally:**
1. `pip install zyndai_agent`
2. Run `python zynd_wrapper.py`
3. Track your agent at zynd.ai

If you have any questions or want me to help you set up the wallet routing, just reply here or shoot me a DM. Happy building! 🚀"""

        # 4. Submit the Pull Request Payload
        pr = original_repo.create_pull(
            title=pr_title,
            body=pr_body,
            head=f"{user.login}:{new_branch_name}",
            base=source_branch
        )
        
        return True, pr.html_url
        
    except Exception as e:
        if "already exists" in str(e).lower():
            return False, "A branch or file with this name already exists in your fork."
        return False, str(e)

def autonomous_pr_campaign(target_keyword="ai-agent", max_deploys=5):
    """
    Scouts GitHub for high-intent repositories and automatically deploys the PR payload.
    Includes aggressive anti-bot delays to protect account standing.
    """
    try:
        token = st.secrets["ZYND_PR_TOKEN"]
    except KeyError:
        return []

    g = Github(token)
    
    # 1. Build the Search Query
    # Looks for Python repos updated in the last 30 days containing your keyword
    thirty_days_ago = (datetime.now(timezone.utc) - timedelta(days=30)).strftime('%Y-%m-%d')
    query = f"{target_keyword} language:python pushed:>{thirty_days_ago}"
    
    try:
        repos = g.search_repositories(query=query, sort="updated", order="desc")
    except Exception as e:
        return [f"Search API Error: {str(e)}"]

    deployed_prs = []
    
    for repo in repos:
        # Stop if we hit our daily limit
        if len(deployed_prs) >= max_deploys:
            break
            
        repo_name = repo.full_name
        
        # 2. Skip massive enterprise repos (they ignore automated PRs)
        if repo.stargazers_count > 5000:
            continue
            
        # 3. Attempt the deployment using your existing function
        success, msg = generate_zynd_pr(repo_name)
        
        if success:
            deployed_prs.append(f"✅ Success: {repo_name} -> {msg}")
            
            # 🛑 CRITICAL ANTI-BAN PROTOCOL 🛑
            # If you fire 10 PRs in 10 seconds, GitHub will permanently ban your token.
            # We must simulate human behavior by sleeping for 45 to 90 seconds between PRs.
            if len(deployed_prs) < max_deploys:
                sleep_time = random.randint(45, 90)
                time.sleep(sleep_time)
        else:
            # If it failed (archived, already PR'd, etc.), just skip to the next one
            pass

    return deployed_prs
