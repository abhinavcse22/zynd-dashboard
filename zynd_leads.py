import time
import requests
import gspread
from datetime import datetime
from zynd_config import ZyndConfig

class TokenSwarm:
    """Manages the 3 dedicated scraping tokens from Streamlit Secrets."""
    def __init__(self):
        self.tokens = ZyndConfig.get_github_tokens()
        if not self.tokens:
            raise ValueError("No GitHub scraping tokens found in Streamlit Secrets.")
        self.idx = 0
        
    def get(self):
        return self.tokens[self.idx]
        
    def rotate(self):
        self.idx = (self.idx + 1) % len(self.tokens)
        print(f"🔄 [RATE LIMIT HIT] Rotating to Scraping Token {self.idx + 1}/{len(self.tokens)}")
        return self.get()

def fetch_builders_graphql(query_str, swarm, max_results=100):
    """Uses GraphQL to search for repos and pull owner emails in bulk."""
    query = """
    query($searchQuery: String!, $cursor: String) {
      search(query: $searchQuery, type: REPOSITORY, first: 50, after: $cursor) {
        pageInfo { endCursor hasNextPage }
        edges {
          node {
            ... on Repository {
              url
              name
              description
              stargazerCount
              owner {
                login
                ... on User { name email bio twitterUsername websiteUrl followers { totalCount } }
              }
            }
          }
        }
      }
    }
    """
    url = "https://api.github.com/graphql"
    results = []
    cursor = None
    has_next = True

    while has_next and len(results) < max_results:
        headers = {"Authorization": f"Bearer {swarm.get()}"}
        variables = {"searchQuery": query_str, "cursor": cursor}
        
        try:
            res = requests.post(url, headers=headers, json={'query': query, 'variables': variables}, timeout=15)
            
            # If rate limited or token fails, rotate and retry
            if res.status_code != 200 or 'errors' in res.json():
                swarm.rotate()
                time.sleep(2)
                continue
            
            data = res.json()['data']['search']
            for edge in data['edges']:
                node = edge['node']
                owner = node.get('owner', {})
                
                # Only extract if it's a User (ignore giant Organization repos)
                if 'email' in owner or 'twitterUsername' in owner: 
                    results.append({
                        "Project URL": node.get('url', ''),
                        "Repo Name": node.get('name', ''),
                        "Description": node.get('description') or "",
                        "Stars": node.get('stargazerCount', 0),
                        "Username": owner.get('login', ''),
                        "Name": owner.get('name') or "",
                        "Email": owner.get('email') or "",
                        "Bio": owner.get('bio') or "",
                        "Twitter": owner.get('twitterUsername') or "",
                        "Followers": owner.get('followers', {}).get('totalCount', 0) if 'followers' in owner else 0
                    })
                    
            cursor = data['pageInfo']['endCursor']
            has_next = data['pageInfo']['hasNextPage']
            print(f"📦 Fetched {len(results)} active builders so far...")
            time.sleep(1) # Polite delay
            
        except Exception as e:
            print(f"⚠️ Network error: {e}. Rotating token...")
            swarm.rotate()
            time.sleep(2)
            
    return results

def harvest_leads():
    """Triggered by the 'Start GitHub Engine' button in Streamlit."""
    print("🚀 Booting GraphQL GitHub Harvester...")
    swarm = TokenSwarm()
    
    # 🎯 The Core GTM Targeting Parameters
    keywords = [
        "AI agent framework", 
        "LLM orchestration", 
        "autonomous agents python",
        "langgraph alternative"
    ]
    all_leads = []
    
    for kw in keywords:
        print(f"\n🔍 Sweeping GitHub for: '{kw}'")
        # 'sort:updated-desc' ensures we only get developers who are coding right now
        search_query = f"{kw} sort:updated-desc" 
        builders = fetch_builders_graphql(search_query, swarm, max_results=50)
        
        for b in builders:
            # Auto-Scoring Engine
            score = 3
            if b['Stars'] > 10: score += 2
            if b['Email'] or b['Twitter']: score += 2
            if 'agent' in b['Description'].lower() or 'llm' in b['Bio'].lower(): score += 2
            
            # Format must match the "GitHub Leads" sheet columns
            all_leads.append([
                b['Project URL'], 
                b['Username'], 
                b['Name'], 
                b['Email'], 
                b['Twitter'],
                b['Bio'], 
                b['Description'], 
                b['Stars'], 
                score, 
                "Hot lead" if score >= 7 else "Warm lead", 
                datetime.now().strftime('%Y-%m-%d %H:%M'), 
                kw
            ])

    if not all_leads:
        print("⚠️ No leads found matching criteria. System idle.")
        return

    # 💾 Secure Database Push
    try:
        creds = ZyndConfig.get_gcp_creds()
        gclient = gspread.authorize(creds)
        sheet = gclient.open_by_key(ZyndConfig.SHEET_ID).worksheet("GitHub Leads")
        
        sheet.append_rows(all_leads, value_input_option='USER_ENTERED')
        print(f"✅ Successfully appended {len(all_leads)} new targeted builders to the CRM.")
        
    except Exception as e:
        print(f"❌ Database Synchronization Error: {e}")
        raise e