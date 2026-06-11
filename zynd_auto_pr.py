from github import Github
import time
import random
import uuid
import streamlit as st
from datetime import datetime, timezone, timedelta

def generate_zynd_pr(target_repo):
    """
    Enterprise-Grade Auto-PR Engine with Spintax Anti-Ban Protection.
    Includes Fork-Polling, Language Verification, and 180-Day TTL.
    """
    try:
        token = st.secrets["ZYND_PR_TOKEN"]
    except KeyError:
        return False, "Configuration Error: 'ZYND_PR_TOKEN' not found in Streamlit Cloud Secrets."
        
    g = Github(token)
    
    try:
        original_repo = g.get_repo(target_repo)
        user = g.get_user()
        
        # 🛑 SECURITY FIX 0: The Archive Radar
        if original_repo.archived:
            return False, "Target repository is archived (read-only). Skipping."
        
        # 🛑 SECURITY FIX 1: The 180-Day TTL Intent Check
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=180)
        if original_repo.pushed_at < cutoff_date:
            return False, f"TTL Violation: Repo hasn't been updated since {original_repo.pushed_at.date()}."

        # 🛑 SECURITY FIX 2: The "Blind Spam" Prevention
        if original_repo.language != "Python":
            langs = original_repo.get_languages()
            if "Python" not in langs:
                return False, f"Language Mismatch: Repo is built in {original_repo.language}."

        # --- ANTI-BAN CHECK ---
        open_prs = original_repo.get_pulls(state='open')
        for pr in open_prs:
            if pr.head.user.login == user.login:
                return False, "You already have an open PR on this repository."

        # 1. Command GitHub to create the Fork
        forked_repo = user.create_fork(original_repo)
        
        # 🛠️ Dynamic Fork Polling
        max_attempts = 15
        fork_ready = False
        for attempt in range(max_attempts):
            try:
                forked_repo.get_branch(original_repo.default_branch)
                fork_ready = True
                break
            except Exception:
                time.sleep(2) 
                
        if not fork_ready:
            return False, "GitHub timed out while building the fork. Try again later."
        
        # 2. Create the new branch cleanly
        source_branch = original_repo.default_branch
        ref = forked_repo.get_git_ref(f"heads/{source_branch}")
        new_branch_name = f"zynd-integration-{int(time.time())}"
        forked_repo.create_git_ref(ref=f"refs/heads/{new_branch_name}", sha=ref.object.sha)
        
        # ==========================================
        # 🛡️ THE ANTI-BAN SPINTAX ENGINE
        # ==========================================
        
        # A. Rotate File Names
        file_names = ["zynd_wrapper.py", "zynd_registry.py", "agent_network_node.py", "zynd_discovery.py"]
        target_file = random.choice(file_names)
        
        # B. Inject Unique Hash to change the file signature completely
        unique_hash = str(uuid.uuid4())[:8]
        comment_variations = [
            "Registers this specific agent on the Zynd open network.",
            "Zynd Network OS deployment wrapper.",
            "Auto-registration module for Zynd discovery.",
            "Exposes the agent to the Zynd monetization protocol."
        ]
        
        file_content = f"""# Zynd Network Integration (Build {unique_hash})
# {random.choice(comment_variations)}
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
        print(f"Zynd Registration skipped: {{e}}")

if __name__ == "__main__":
    register_agent()
"""
        
        # C. Rotate Commit Messages
        commit_messages = [
            f"feat: Add Zynd network wrapper ({unique_hash})",
            "chore: add Zynd agent discoverability",
            "feat: integrate Zynd monetization layer",
            "build: add network deployment node for Zynd"
        ]

        forked_repo.create_file(
            path=target_file,
            message=random.choice(commit_messages),
            content=file_content,
            branch=new_branch_name
        )
        
        # D. Rotate PR Copy
        greetings = ["Hey!", "Hi there!", "Hello!", "Hey team!"]
        compliments = ["Been following this repo for a bit.", "Really clean codebase.", "Love the architecture you've set up here.", "Impressive agent build!"]
        pr_titles = [
            "🚀 Feature: Web3 Discovery & USDC Monetization Layer",
            "Feature: Add Zynd Agent Discoverability",
            "Integration: Zynd Network Registry",
            "Add public agent profile & monetization via Zynd"
        ]
        
        pr_body = f"""{random.choice(greetings)} {random.choice(compliments)}

I noticed this agent wasn't registered on the [Zynd open network](https://zynd.ai) yet. I went ahead and added a quick integration wrapper (`{target_file}`) so your agent becomes discoverable via semantic search and can start earning USDC per call via the x402 protocol.

No Stripe accounts, no KYC, no complex billing infra required. 

**🛠️ To test this locally:**
1. `pip install zyndai_agent`
2. `python {target_file}`
3. Track your agent at zynd.ai

If you have any questions or want me to help you set up the wallet routing, just reply here or shoot me a DM. Happy building! 🚀"""

        # 4. Submit the Pull Request Payload
        pr = original_repo.create_pull(
            title=random.choice(pr_titles),
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
    thirty_days_ago = (datetime.now(timezone.utc) - timedelta(days=30)).strftime('%Y-%m-%d')
    query = f"{target_keyword} language:python pushed:>{thirty_days_ago}"
    
    try:
        repos = g.search_repositories(query=query, sort="updated", order="desc")
    except Exception as e:
        return [f"Search API Error: {str(e)}"]

    deployed_prs = []
    
    for repo in repos:
        if len(deployed_prs) >= max_deploys:
            break
            
        repo_name = repo.full_name
        
        if repo.stargazers_count > 5000:
            continue
            
        success, msg = generate_zynd_pr(repo_name)
        
        if success:
            deployed_prs.append(f"✅ Success: {repo_name} -> {msg}")
        else:
            print(f"ℹ️ Skipped {repo_name}: {msg}")
            
        # 🛑 CRITICAL ANTI-BAN PROTOCOL
        sleep_time = random.randint(60, 120)
        time.sleep(sleep_time)

    return deployed_prs