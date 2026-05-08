import urllib.parse

def get_sniper_urls():
    """Generates the exact mathematical Boolean queries to bypass Twitter algorithms."""
    
    query_bip = '("building an AI agent" OR "my AI agent" OR "shipping my agent") ("LangChain" OR "CrewAI" OR "Python") -filter:links'
    query_pain = '("LangGraph" OR "CrewAI" OR "Autogen" OR "AI agent") ("stuck" OR "error" OR "hallucination" OR "issue") -filter:links'
    query_comp = '("using CrewAI" OR "tried LangChain" OR "using Autogen") ("slow" OR "alternative" OR "complex" OR "hard")'

    return {
        "build_in_public": f"https://twitter.com/search?q={urllib.parse.quote(query_bip)}&f=live",
        "pain_points": f"https://twitter.com/search?q={urllib.parse.quote(query_pain)}&f=live",
        "competitor_poaching": f"https://twitter.com/search?q={urllib.parse.quote(query_comp)}&f=live"
    }
