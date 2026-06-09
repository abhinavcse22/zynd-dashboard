"""AI reasoning module - all Claude calls live here.

Two reasoning stages:

STAGE 1 - Post Scoring:
  Claude reads a LinkedIn post and decides:
  - Is the poster a real developer/builder (not a content marketer)?
  - Does the post signal a pain point that Zynd solves?
  - What tier are they (1/2/3)?
  - What specific angle to use in the DM?

STAGE 2 - DM Generation:
  Claude writes a personalized connection note + follow-up DM.
  Personalization is based on the post angle (not the post text verbatim)
  so it never feels like surveillance.

Running modes:
  - Claude Code (interactive): prompts are printed for Claude to reason over inline.
  - Automated (ANTHROPIC_API_KEY set): calls the Anthropic API directly.
"""

import json
import os

try:
    import requests as _requests
    _requests_available = True
except ImportError:
    _requests_available = False

from config import ANTHROPIC_API_KEY, PERSONA_JTBD, ZYND_VALUE_PROPS


# =========================================================================
# STAGE 1: Post Scoring
# =========================================================================

POST_SCORING_SYSTEM = """You are a growth analyst for Zynd.ai — an open agent network that gives AI agents built in LangChain, CrewAI, LangGraph, n8n, and other frameworks four things:
1. A discoverable ZNS name (like DNS for agents)
2. A verifiable DID identity
3. Pay-per-use x402/USDC micropayments with no Stripe account needed
4. A permanent HTTPS endpoint via deployer.zynd.ai

The registration takes 30 seconds: `pip install zyndai-agent` + one register() call.

Your job: read a LinkedIn post and assess whether the person who posted it is a strong early-adopter candidate for Zynd.ai.

STRONG early adopter signals (any one is enough):
- They are actively building AI agents (LangChain, CrewAI, LangGraph, AutoGen, PydanticAI)
- They built an MCP server and want to expose it publicly
- They use n8n for AI automation workflows
- They are frustrated with agent monetization (charging per call, billing infra)
- They are frustrated with agent discoverability (nobody finds their agent)
- They want agents to talk to each other across frameworks
- They are comfortable with USDC/crypto and building AI tools (Web3 + AI stack)
- They are RevOps/GTM engineers building AI-powered workflow stacks

SKIP signals (do not reach out):
- Pure content marketer / thought leader with no technical content
- They are building with consumer AI tools only (ChatGPT, Copilot users - not builders)
- The post is a job posting, press release, or company announcement
- They work at a very large enterprise where bottom-up adoption is unlikely
- The post shows no genuine technical engagement with agent frameworks
- They are clearly a student with no shipped work yet

ICP fit for Zynd:
- STRONG: Engineers/CTOs/Indie Hackers actively building and shipping agents at SMBs or solo
- PARTIAL: RevOps/GTM engineers using AI workflows; Solutions Architects designing agent systems
- SKIP: Non-technical, pure enterprise, no evidence of building

Signal type mapping:
- agent_builder: Building/shipping AI agents with LangChain, CrewAI, LangGraph, AutoGen
- monetization_pain: Frustrated about charging for agents, billing infra for agents
- discovery_pain: Frustrated nobody finds their agent, wants distribution
- interop_pain: Wants agents to talk to each other across frameworks
- mcp_builder: Building MCP servers
- n8n_builder: Building AI workflows in n8n
- web3_builder: Comfortable with USDC/Base, building AI tools
- revops_gtm: RevOps/GTM engineer building AI-powered automation

Respond with ONLY valid JSON, no markdown, no explanation."""

POST_SCORING_SCHEMA = """{
  "should_reach_out": true or false,
  "skip_reason": "string or null - why skipping if false",
  "signal_type": "agent_builder | monetization_pain | discovery_pain | interop_pain | mcp_builder | n8n_builder | web3_builder | revops_gtm | null",
  "tier": 1 or 2 or 3,
  "icp_fit": "strong | partial | skip",
  "icp_reasoning": "one sentence",
  "persona_guess": "string - best guess at their job title based on post and headline",
  "post_angle": "one sentence - what specific thing they are building/frustrated about (used for DM personalization)",
  "engagement_signal": "one sentence - what the post reveals about their current work or pain",
  "frameworks_mentioned": ["list of AI frameworks or tools they mention or clearly use"]
}"""

def build_post_scoring_prompt(post: dict) -> dict:
    """Build the post scoring prompt."""
    return {
        "system": POST_SCORING_SYSTEM,
        "user": f"""Score this LinkedIn post for Zynd.ai early-adopter fit.

POSTER:
- Name: {post.get('author_name', 'Unknown')}
- Headline: {post.get('author_headline', '')}
- Location: {post.get('author_location', '')}
- Company: {post.get('company_name', '')}
- LinkedIn: {post.get('author_linkedin_url', '')}

POST TEXT:
{post.get('text', '')}

POST METADATA:
- Posted at: {post.get('posted_at', '')}
- Likes: {post.get('likes', 0)}
- Comments: {post.get('comments', 0)}
- Signal type hint (from search query that found this post): {post.get('signal_type', '')}

Respond with this exact JSON schema:
{POST_SCORING_SCHEMA}""",
    }


# =========================================================================
# STAGE 2: DM Generation
# =========================================================================

DM_GENERATION_SYSTEM = """You are writing LinkedIn DMs for Zynd.ai - an open agent network that wraps AI agents built in LangChain/CrewAI/LangGraph/n8n into discoverable, paid endpoints.

The one-line pitch: "30 seconds to wrap your agent, free distribution via ZNS, get paid per call in USDC - no Stripe."

Key value props by signal:
- agent_builder: ZNS name + pay-per-call endpoint. Their agent stops sitting on a hard drive.
- monetization_pain: x402 micropayments on Base - HTTP-native, no Stripe, no account setup on either side.
- discovery_pain: ZNS is discoverable via semantic search - like DNS + Google for agents.
- interop_pain: Every Zynd agent gets a standard HTTPS endpoint callable from any framework.
- mcp_builder: Any MCP server wraps in one line - gets a public endpoint + paid per tool call.
- n8n_builder: Native n8n-nodes-zyndai integration - register directly from the workflow.
- web3_builder: x402 + USDC on Base - exactly the payment primitive they already understand.
- revops_gtm: Makes AI GTM workflow components composable - scoring agent calls enrichment agent, etc.

RULES - follow exactly:
1. No em dashes. Hyphens only.
2. No emojis.
3. No "I hope this finds you well" or generic openers.
4. Never say "I saw your post" or "I noticed you posted about" - that feels like surveillance.
5. Anchor on the topic/angle they care about, not their specific post.
6. Be peer-to-peer, not BDR-to-prospect. You are a builder talking to a builder.
7. No buzzword stacking. No "leveraging synergies". Short sentences.
8. Connection note: one sentence, curiosity gap, under 300 characters.
9. Follow-up: one short paragraph, problem -> what Zynd does about it -> low-friction ask. Under 800 characters.
10. If they use a specific framework (LangChain, CrewAI, n8n), name it - shows you know the space.

Respond with ONLY valid JSON, no markdown."""

def build_dm_prompt(
    poster: dict,
    scoring: dict,
    profile_info: dict,
) -> dict:
    """Build the DM generation prompt."""
    signal_type = scoring.get("signal_type", "agent_builder")
    value_prop = ZYND_VALUE_PROPS.get(signal_type, ZYND_VALUE_PROPS.get("agent_builder", {}))

    persona_guess = scoring.get("persona_guess", "")
    jtbd = ""
    for key, val in PERSONA_JTBD.items():
        if key.lower() in persona_guess.lower():
            jtbd = val
            break

    # Merge framework signals from Claude scoring + enriched profile
    frameworks = list(set(scoring.get("frameworks_mentioned", [])))
    if profile_info.get("uses_langchain"):
        frameworks.append("LangChain")
    if profile_info.get("uses_crewai"):
        frameworks.append("CrewAI")
    if profile_info.get("uses_n8n"):
        frameworks.append("n8n")
    frameworks = list(dict.fromkeys(frameworks))  # dedupe, preserve order

    about_snippet = profile_info.get("about", "")[:200]
    skills_snippet = ", ".join(profile_info.get("skills", [])[:10])

    return {
        "system": DM_GENERATION_SYSTEM,
        "user": f"""Write a LinkedIn DM for this prospect.

PROSPECT:
- Name: {poster.get('author_name', '')}
- Headline: {profile_info.get('headline') or poster.get('author_headline', '')}
- Current role: {profile_info.get('current_role') or persona_guess}
- Location: {profile_info.get('location') or poster.get('author_location', '')}
- About (first 200 chars): {about_snippet}
- Skills: {skills_snippet}
- Their JTBD: {jtbd}

COMPANY:
- Name: {profile_info.get('current_company') or poster.get('company_name', '')}
- Uses LangChain/LangGraph: {profile_info.get('uses_langchain', False)}
- Uses CrewAI: {profile_info.get('uses_crewai', False)}
- Uses n8n: {profile_info.get('uses_n8n', False)}
- Uses OpenAI/GPT: {profile_info.get('uses_openai', False)}
- Web3/crypto background: {profile_info.get('uses_web3', False)}

SIGNAL CONTEXT:
- Signal type: {signal_type}
- Post angle (what they care about): {scoring.get('post_angle', '')}
- Engagement signal: {scoring.get('engagement_signal', '')}
- Frameworks they use: {', '.join(frameworks) if frameworks else 'unknown'}
- ICP fit: {scoring.get('icp_fit', '')}

ZYND ANGLE FOR THIS SIGNAL:
- Their core pain: {value_prop.get('core_pain', '')}
- Zynd's answer: {value_prop.get('zynd_angle', '')}
- Hook: {value_prop.get('hook', '')}
- Tier 1 message angle: {value_prop.get('message_angle_t1', '')}

Respond with this exact JSON:
{{"connection_note": "string under 300 chars", "followup_msg": "string under 800 chars"}}""",
    }


# =========================================================================
# Execution helpers
# =========================================================================

def score_post(post: dict) -> dict:
    """Run post scoring. API mode if ANTHROPIC_API_KEY is set; else returns prompt for Claude Code."""
    prompt = build_post_scoring_prompt(post)
    if ANTHROPIC_API_KEY:
        try:
            return _call_claude_api(prompt["system"], prompt["user"], max_tokens=600)
        except Exception as e:
            print(f"    [Claude] API error scoring post: {e}")
            return _fallback_scoring(post)
    return _fallback_scoring(post)


def generate_dm(poster: dict, scoring: dict, profile_info: dict) -> dict:
    """Generate personalized DM. API mode if ANTHROPIC_API_KEY is set."""
    prompt = build_dm_prompt(poster, scoring, profile_info)
    if ANTHROPIC_API_KEY:
        try:
            result = _call_claude_api(prompt["system"], prompt["user"], max_tokens=500)
            for key in result:
                if isinstance(result[key], str):
                    result[key] = result[key].replace("—", "-").replace("–", "-")
            return result
        except Exception as e:
            print(f"    [Claude] API error generating DM: {e}")
            return _fallback_dm(poster)
    return _fallback_dm(poster)


def _call_claude_api(system_prompt: str, user_prompt: str, max_tokens: int = 800) -> dict:
    """Call the Anthropic API directly for automated runs."""
    if not ANTHROPIC_API_KEY or not _requests_available:
        raise RuntimeError("ANTHROPIC_API_KEY not set or requests not available.")

    r = _requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": "claude-sonnet-4-6",
            "max_tokens": max_tokens,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        },
        timeout=60,
    )
    r.raise_for_status()
    text = "".join(
        block["text"] for block in r.json().get("content", [])
        if block.get("type") == "text"
    )
    text = text.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
    return json.loads(text)


def _fallback_scoring(post: dict) -> dict:
    """Minimal fallback when API is unavailable - marks for manual review."""
    return {
        "should_reach_out": True,
        "skip_reason": None,
        "signal_type": post.get("signal_type", "agent_builder"),
        "tier": 2,
        "icp_fit": "partial",
        "icp_reasoning": "Fallback - manual review needed",
        "persona_guess": "",
        "post_angle": post.get("text", "")[:100],
        "engagement_signal": "Fallback",
        "frameworks_mentioned": [],
    }


def _fallback_dm(poster: dict) -> dict:
    name = poster.get("author_name", "").split()[0] if poster.get("author_name") else ""
    return {
        "connection_note": "Quick question about agent distribution - building something in this space and think it's relevant to what you're working on.",
        "followup_msg": f"Hi {name}, most agents built with LangChain or CrewAI have the same problem - no distribution and no payment rail without building a full SaaS. Zynd wraps any agent into a discoverable ZNS endpoint with x402 micropayments in about 30 seconds. Worth a look?",
    }
