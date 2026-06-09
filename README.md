# Zynd.ai LinkedIn Social Listening Outbound Agent

AI-powered social listening pipeline that finds Zynd.ai early adopters from yesterday's LinkedIn posts, scores them with Claude, and pushes personalized DMs to SendPilot.

## Install as a Claude Code plugin

This is a Claude Code plugin. To install it:

1. Install [Claude Code](https://claude.ai/download) if you haven't already
2. Open Claude Code in any directory
3. Paste this message into Claude Code:

```
Install this plugin: https://github.com/yashasvisaxena3-jpg/zynd-ai-linkedin-outbound-agent-plugin
```

Claude Code will clone the repo and make the `/social-listen` command available. Then type `/social-listen` and it will walk you through setup.

**Or run it directly without installing as a plugin:**

```bash
git clone https://github.com/yashasvisaxena3-jpg/zynd-ai-linkedin-outbound-agent-plugin
cd zynd-ai-linkedin-outbound-agent-plugin
pip install -r requirements.txt
cp .env.example .env
# fill in .env, then:
python main.py --dry-run --limit=10
```

---

## What it does

1. **Scrapes** yesterday's LinkedIn posts via Apify - searching for signals that someone is building AI agents, frustrated with agent monetization/discoverability, or working with MCP/n8n/LangChain/CrewAI
2. **Scores** every post with Claude - is this person a real builder? What tier? What pain does Zynd solve for them?
3. **Enriches** each poster's LinkedIn profile via Apify (same account, no extra cost) - full profile, about section, skills, framework signals
4. **Generates** a personalized DM via Claude - anchored on their specific building angle, never "I saw your post"
5. **Pushes** qualified leads + DMs to SendPilot - which handles the connection request and follow-up sequence

---

## Setup checklist

### 1. Apify API token

Sign up at [apify.com](https://apify.com) (free tier gives $5 of credits to start).

Go to **console.apify.com → Settings → Integrations → API token** and copy the token into `.env`:

```
APIFY_API_TOKEN=apify_api_xxxxxx
```

---

### 2. SendPilot

Sign up at [sendpilot.ai](https://sendpilot.ai).

**Step 1 - Get your API key:**
Go to SendPilot → **Settings → API Keys → Create new key** and paste it into `.env`:

```
SENDPILOT_API_KEY=sp_xxxxxx
```

**Step 2 - Create a campaign:**
In SendPilot, create a new LinkedIn outreach campaign with this exact sequence:
- **Step 1 (Connection request):** Use the variable `{connection_note}` as the message
- **Step 2 (After connection accepted):** Use the variable `{followup_msg}` as the message

Open the campaign, copy the campaign ID from the URL (it looks like a number or UUID), and paste it into `.env`:

```
SENDPILOT_CAMPAIGN_ID=12345
```

---

### 3. Anthropic API key (only for automated/scheduled runs)

If you run this interactively inside Claude Code, **you do not need this** — Claude reasons inline and no API key is required.

If you want to run it on a schedule (cron job, GitHub Actions, etc.), get an API key from [console.anthropic.com](https://console.anthropic.com) and add it:

```
ANTHROPIC_API_KEY=sk-ant-xxxxxx
```

---

## Running it

```bash
# Preview first - no SendPilot push, shows sample DMs
python main.py --dry-run --limit=10

# Test a single signal type
python main.py --dry-run --signal=agent_builder --limit=10

# Live run - pushes to SendPilot
python main.py --limit=30

# Full daily run
python main.py
```

Check `output/review.csv` after any run to see all scored posts and generated DMs before going live.

---

## Signal types - who we listen for

| Signal | Who | Tier |
|--------|-----|------|
| `agent_builder` | Actively shipping LangChain / CrewAI / LangGraph / AutoGen agents | 1 |
| `monetization_pain` | Frustrated they can't charge for their agent without building Stripe infra | 1 |
| `discovery_pain` | Frustrated nobody finds their agent | 1 |
| `interop_pain` | Wants agents to call each other across frameworks | 1 |
| `mcp_builder` | Building MCP servers - wraps directly to Zynd in one line | 1 |
| `n8n_builder` | n8n AI workflow builders - Zynd has native n8n-nodes-zyndai | 2 |
| `web3_builder` | Web3 devs building AI - already speak USDC/Base | 2 |
| `revops_gtm` | RevOps/GTM engineers on AI-powered workflow stacks | 2 |

---

## File structure

```
zynd-ai-linkedin-outbound-agent-plugin/
  .env                          # Your API keys (gitignored)
  .env.example                  # Template - copy this to .env
  config.py                     # Config loader
  main.py                       # Pipeline orchestrator (6 steps)
  ai_reasoning.py               # All Claude AI calls (post scoring + DM generation)
  requirements.txt
  clients/
    apify.py                    # LinkedIn post scraper via Apify
    linkedin_enrichment.py      # Profile enrichment via Apify (same token)
    sendpilot.py                 # Push leads to SendPilot
  data/
    post_signal_keywords.json   # Search queries per signal type
    persona_jtbd.json           # Job-to-be-done per persona (used in DM prompt)
    zynd_value_props.json       # Zynd value props per signal type (used in DM prompt)
  output/
    posts_raw.json              # Raw Apify output
    scored_posts.json           # After Claude scoring
    drafts.json                 # Full pipeline output per run
    review.csv                  # Human-readable review sheet
    seen_profiles.json          # Deduplication cache (already-contacted profiles)
  .claude/
    commands/
      social-listen.md          # Claude Code /social-listen skill
```

---

## Running on a daily schedule

```cron
# Every morning at 9 AM - catches yesterday's posts
0 9 * * * cd /path/to/zynd-ai-linkedin-outbound-agent-plugin && python main.py >> output/logs.txt 2>&1
```

---

## Troubleshooting

**0 posts found:** Try increasing `LOOKBACK_DAYS` to 2-3 for initial testing. If consistently empty, verify your `APIFY_API_TOKEN` is valid and the `harvestapi/linkedin-post-search` actor is available in your Apify account.

**All posts scored "skip":** Check `output/posts_raw.json` to confirm posts have real text content. Try different signal types with `--signal=agent_builder` or broaden queries.

**SendPilot push fails:** Confirm the campaign is **Active** (not paused/draft) in SendPilot. Double-check `SENDPILOT_CAMPAIGN_ID` matches the campaign exactly.

---

## License

MIT
