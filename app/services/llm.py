"""Resume suggestions: Claude when an API key is configured, rules otherwise."""

import json
import logging

import httpx

from app.config import get_settings
from app.services.matcher import MatchAnalysis

log = logging.getLogger(__name__)

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"

PROMPT = """You are a career coach reviewing a resume against a job description.
Matched skills: {matched}
Missing skills: {missing}

Give 3 to 5 short, specific, honest suggestions to improve this resume for this job.
Never suggest claiming skills the candidate does not have; for missing skills suggest
learning them or showing related experience. Reply with only a JSON array of strings.

RESUME:
{resume}

JOB DESCRIPTION:
{job}"""


def rule_based_suggestions(analysis: MatchAnalysis) -> list[str]:
    tips: list[str] = []
    if analysis.missing_skills:
        top = ", ".join(analysis.missing_skills[:3])
        tips.append(
            f"The job asks for {top}. If you have used them, name them explicitly; "
            "if not, consider a small project to learn them."
        )
    if analysis.matched_skills:
        strongest = ", ".join(analysis.matched_skills[:3])
        tips.append(f"Move your strongest matches ({strongest}) into your summary and top bullet points.")
    if analysis.score < 50:
        tips.append("Mirror the job description's wording in your bullets where it truthfully describes your work.")
    tips.append("Quantify impact in each bullet (users, latency, time saved, % improvement).")
    return tips


def llm_suggestions(
    resume: str, job: str, analysis: MatchAnalysis, client: httpx.Client | None = None
) -> list[str] | None:
    settings = get_settings()
    if not settings.anthropic_api_key:
        return None
    prompt = PROMPT.format(
        matched=", ".join(analysis.matched_skills) or "none",
        missing=", ".join(analysis.missing_skills) or "none",
        resume=resume[:6000],
        job=job[:6000],
    )
    own_client = client is None
    client = client or httpx.Client(timeout=30)
    try:
        resp = client.post(
            ANTHROPIC_URL,
            headers={
                "x-api-key": settings.anthropic_api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": settings.anthropic_model,
                "max_tokens": 600,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        resp.raise_for_status()
        text = resp.json()["content"][0]["text"]
        tips = json.loads(text[text.find("[") : text.rfind("]") + 1])
        return [str(t) for t in tips if str(t).strip()][:5] or None
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
        log.warning("LLM suggestions failed, falling back to rules: %s", exc)
        return None
    finally:
        if own_client:
            client.close()


def suggestions(resume: str, job: str, analysis: MatchAnalysis) -> tuple[list[str], str]:
    tips = llm_suggestions(resume, job, analysis)
    if tips:
        return tips, "llm"
    return rule_based_suggestions(analysis), "rules"
