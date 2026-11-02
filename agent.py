"""AI Sales Copilot agent.

A three-step agent workflow for one lead:
  1. research  - read the lead's company website (public info only)
  2. score     - rate fit against the ICP and find "why now" signals
  3. draft     - write a short email and a 30-second call opener
A human rep reviews and approves every draft before anything is sent.

If no ANTHROPIC_API_KEY is set, the agent runs in mock mode so the app
can be demoed without a key.
"""

import json
import os
import re

import requests
from bs4 import BeautifulSoup

MODEL = os.getenv("COPILOT_MODEL", "claude-sonnet-5-5")


# ---------- step 1: research ----------

def research_company(url: str, max_chars: int = 4000) -> str:
    """Fetch a company homepage and return its visible text (public info only)."""
    if not url:
        return ""
    if not url.startswith("http"):
        url = "https://" + url
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0 (sales-copilot demo)"})
        resp.raise_for_status()
    except requests.RequestException as exc:
        return f"(Could not load website: {exc.__class__.__name__})"
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "noscript"]):
        tag.decompose()
    text = re.sub(r"\s+", " ", soup.get_text(" ")).strip()
    return text[:max_chars]


# ---------- Claude helper ----------

def _client(api_key=None):
    key = api_key or os.getenv("ANTHROPIC_API_KEY")
    if not key:
        return None
    import anthropic
    return anthropic.Anthropic(api_key=key)


def _ask_json(system: str, prompt: str, api_key=None, max_tokens: int = 800) -> dict:
    """Call Claude and parse a JSON object from its reply."""
    client = _client(api_key)
    msg = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(block.text for block in msg.content if getattr(block, "type", "") == "text")
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise ValueError("Model did not return JSON: " + text[:200])
    return json.loads(match.group(0))


# ---------- step 2: score ----------

SCORE_SYSTEM = (
    "You are an SDR research assistant. Score how well a B2B lead fits the seller's "
    "ideal customer profile (ICP). Use only the information provided; never invent facts. "
    "If information is missing, say so and lower your confidence. Reply with JSON only."
)


def score_lead(lead: dict, research: str, icp: str, offering: str, api_key=None) -> dict:
    if _client(api_key) is None:
        return _mock_score(lead)
    prompt = f"""What we sell:
{offering}

Ideal customer profile:
{icp}

Lead:
{json.dumps(lead, ensure_ascii=False)}

Company website text (may be partial):
{research or '(none)'}

Return JSON with keys:
- "score": integer 0-100 (fit with the ICP)
- "reason": one sentence explaining the score
- "why_now": a timely signal from the data (hiring, funding, launch, expansion) or "none found"
- "pain_point": the most likely problem this person has that we solve
- "confidence": "high", "medium" or "low"
"""
    return _ask_json(SCORE_SYSTEM, prompt, api_key)


# ---------- step 3: draft ----------

DRAFT_SYSTEM = (
    "You write short, specific B2B outreach for an SDR. Rules: the email is under 75 words, "
    "the first sentence is about the prospect, not us; mention one problem only; end with one "
    "small ask (a 20-minute call). No hype, no invented facts or numbers. Reply with JSON only."
)


def draft_outreach(lead: dict, scored: dict, offering: str, sender: str, api_key=None) -> dict:
    if _client(api_key) is None:
        return _mock_draft(lead, scored, sender, offering)
    prompt = f"""What we sell:
{offering}

Lead:
{json.dumps(lead, ensure_ascii=False)}

Research findings:
{json.dumps(scored, ensure_ascii=False)}

Sender name: {sender}

Return JSON with keys:
- "subject": email subject line, under 7 words
- "email": the email body, under 75 words, signed with the sender name
- "call_opener": a 30-second cold-call opener that asks permission and ends with an open question
"""
    return _ask_json(DRAFT_SYSTEM, prompt, api_key)


# ---------- the agent ----------

def run_agent(lead: dict, icp: str, offering: str, sender: str, use_web: bool = True, api_key=None) -> dict:
    """Run research -> score -> draft for one lead and return everything for review."""
    research = research_company(lead.get("website", "")) if use_web else ""
    scored = score_lead(lead, research, icp, offering, api_key)
    draft = draft_outreach(lead, scored, offering, sender, api_key)
    return {"research": research, **scored, **draft, "status": "Needs review"}


# ---------- mock mode (no API key) ----------

def _mock_score(lead: dict) -> dict:
    notes = lead.get("notes") or ""
    clauses = [c.strip() for c in notes.split(";") if c.strip()]
    score, why_now = 50, "none found"
    for word, pts in [("hiring", 20), ("raised", 15), ("series", 10), ("launch", 10),
                      ("expand", 10), ("new vp", 10), ("ai", 5)]:
        hit = next((c for c in clauses if word in c.lower().split() or word in c.lower()[:40]), None)
        if hit:
            score += pts
            if why_now == "none found":
                why_now = hit
    return {
        "score": min(score, 95),
        "reason": "Mock score based on signals in the notes (add an API key for real analysis).",
        "why_now": why_now,
        "pain_point": "See notes; add an API key for a real analysis.",
        "confidence": "low",
    }


def _mock_draft(lead: dict, scored: dict, sender: str, offering: str = "") -> dict:
    first = (lead.get("name") or "there").split()[0]
    company = lead.get("company", "your team")
    is_data = "analytics" in offering.lower()
    pain = ("business teams often wait days on analysts for answers"
            if is_data else "reps often lose hours on accounts that aren't ready to buy")
    pitch = ("We help data teams and business users get trusted answers in minutes"
             if is_data else "We help reps see which accounts to call first")
    question = ("How are business teams getting answers from your data today?"
                if is_data else "How is your team deciding which accounts to call first today?")
    return {
        "subject": f"Idea for {company}",
        "email": (
            f"Hi {first},\n\nNoticed {company}: {scored['why_now'][:1].lower() + scored['why_now'][1:]}. In that situation, {pain}.\n\n"
            f"{pitch}. Worth a 20-minute look next week?\n\n{sender}"
        ),
        "call_opener": (
            f"Hi {first}, this is {sender}. I know I'm calling out of the blue; can I have 30 seconds "
            f"to share why I called, and you tell me if it's worth a longer chat? ... {question}"
        ),
    }
