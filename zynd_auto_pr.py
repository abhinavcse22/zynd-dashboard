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
    token = st.secrets["github"]["tokens"][0]
    g = Github(token)
    
    try:
        original_repo = g.get_repo(target_repo)
        user = g.get_user()
        
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
        file_content = """# Zynd Network Wrapper
# This file registers your agent on the Zynd x402 network for discovery and monetization.
import zyndai_agent

def register_agent():
    agent = zyndai_agent.ZyndAgent(
        name="My Agent",
        description="Auto-registered to the Zynd open network."
    )
    agent.deploy()
    print("🚀 Agent is live on ZNS!")

if __name__ == "__main__":
    register_agent()
"""
        forked_repo.create_file(
            path="zynd_wrapper.py",
            message="feat: Add Zynd x402 monetization wrapper",
            content=file_content,
            branch=new_branch_name
        )
        
        # --- SPINTAX GENERATION ---
        greetings = ["Hi!", "Hey there!", "Hello!", "Hey!"]
        compliments = ["Awesome project.", "Really love what you've built here.", "Great work on this repo.", "Impressive agent setup!"]
        closings = ["Happy to answer any questions or help test it!", "Let me know if you have any questions!", "Cheers!", "Happy building!"]
        
        pr_title = f"🚀 Feature: Add Zynd Network Discovery & USDC Monetization"
        
        pr_body = f"""{random.choice(greetings)} {random.choice(compliments)}

I noticed this agent wasn't registered on the [Zynd open network](https://zynd.ai). I went ahead and added a quick 1-line wrapper (`zynd_wrapper.py`) so your agent becomes discoverable via semantic search and can earn USDC per call via the x402 protocol. 

No Stripe account or billing infra required. {random.choice(closings)}"""

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
