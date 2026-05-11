from github import Github
import time
import random
import streamlit as st

def generate_zynd_pr(target_repo):
    """
    Forks a repo, injects the Zynd wrapper, and submits a Pull Request.
    Includes anti-spam randomization and duplicate checks to protect your account.
    """
    token = st.secrets["github"]["tokens"][0]
    g = Github(token)
    
    try:
        original_repo = g.get_repo(target_repo)
        user = g.get_user()
        
        # --- ANTI-BAN CHECK 1: Prevent Duplicate PRs ---
        # Check if you already have an open PR on this repo
        open_prs = original_repo.get_pulls(state='open', head=f"{user.login}")
        if open_prs.totalCount > 0:
            return False, "You already have an open PR on this repository. Aborting to prevent spam."

        # 1. Create a Fork
        forked_repo = user.create_fork(original_repo)
        time.sleep(5) # Delay to let GitHub servers catch up
        
        # 2. Create a new branch
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
        
        # --- ANTI-BAN CHECK 2: Spintax Randomization ---
        # Randomize the greetings and formatting so GitHub's spam filter doesn't detect a pattern
        greetings = ["Hi!", "Hey there!", "Hello!", "Hey!"]
        compliments = ["Awesome project.", "Really love what you've built here.", "Great work on this repo.", "Impressive agent setup!"]
        closings = ["Happy to answer any questions or help test it!", "Let me know if you have any questions!", "Cheers!", "Happy building!"]
        
        pr_title = f"🚀 Feature: Add Zynd Network Discovery & USDC Monetization"
        
        pr_body = f"""{random.choice(greetings)} {random.choice(compliments)}

I noticed this agent wasn't registered on the [Zynd open network](https://zynd.ai). I went ahead and added a quick 1-line wrapper (`zynd_wrapper.py`) so your agent becomes discoverable via semantic search and can earn USDC per call via the x402 protocol. 

No Stripe account or billing infra required. {random.choice(closings)}"""

        # 4. Submit the Pull Request
        pr = original_repo.create_pull(
            title=pr_title,
            body=pr_body,
            head=f"{user.login}:{new_branch_name}",
            base=source_branch
        )
        
        return True, pr.html_url
        
    except Exception as e:
        # Catch standard GitHub API errors gracefully
        if "already exists" in str(e).lower():
            return False, "A branch or file with this name already exists in your fork."
        return False, str(e)
