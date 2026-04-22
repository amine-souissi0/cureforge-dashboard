"""
Grant Agent — Grants.gov opportunity discovery + GPT-4 narrative drafting.

What this does automatically:
  - Searches Grants.gov REST API for relevant funding opportunities
  - Drafts a project narrative / specific aims using GPT-4

What still requires human action:
  - Final SF424 submission via Grants.gov Workspace or NIH ASSIST
    (S2S SOAP submission requires institutional digital certificate)

Usage:
    from agents.grant_agent import discover_grants, draft_narrative, save_application
"""

import json
import logging
from pathlib import Path
from typing import Optional

import requests
from openai import OpenAI

from config.settings import settings

logger = logging.getLogger(__name__)

_client = OpenAI(api_key=settings.openai_api_key)

GRANTS_GOV_SEARCH_URL = "https://api.grants.gov/v2/api/search2"
NIH_REPORTER_URL = "https://api.reporter.nih.gov/v2/projects/search"

_NARRATIVE_SYSTEM_PROMPT = """\
You are an expert NIH/NSF grant writer specializing in longevity and biotech research.
Given a funding opportunity and project information, write a concise 1-page
Project Narrative / Specific Aims following NIH formatting conventions:
  • Opening paragraph — the scientific problem and significance
  • Specific Aim 1, 2, 3 — each with objective and expected outcome
  • Closing paragraph — innovation and long-term impact
Write clearly, use active voice, and stay under 750 words.\
"""


def discover_grants(keywords: str, limit: int = 10) -> list[dict]:
    """
    Search Grants.gov for open funding opportunities matching keywords.

    Args:
        keywords: free-text search string (e.g. "longevity aging biomarkers")
        limit:    max number of results (max 25 per Grants.gov API)

    Returns:
        List of opportunity dicts with keys: opportunity_id, title, agency,
        close_date, award_ceiling, description.
    """
    payload = {
        "keyword": keywords,
        "rows": min(limit, 25),
        "oppStatuses": "posted",
        "sortBy": "openDate",
        "sortOrder": "desc",
    }

    try:
        resp = requests.post(GRANTS_GOV_SEARCH_URL, json=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        logger.error("Grants.gov API error: %s", exc)
        return []

    opportunities = []
    for hit in data.get("data", {}).get("hits", []):
        opportunities.append(
            {
                "opportunity_id": hit.get("id", ""),
                "title": hit.get("title", ""),
                "agency": hit.get("agencyName", ""),
                "close_date": hit.get("closeDate", ""),
                "award_ceiling": hit.get("awardCeiling", ""),
                "synopsis": hit.get("synopsis", ""),
                "url": f"https://www.grants.gov/search-results-detail/{hit.get('id', '')}",
            }
        )

    logger.info("Found %d grant opportunities for '%s'", len(opportunities), keywords)
    return opportunities


def search_nih_reporter(keywords: str, limit: int = 10) -> list[dict]:
    """
    Search NIH RePORTER for existing funded projects (useful for landscape analysis).

    Args:
        keywords: search text
        limit: max results

    Returns:
        List of project dicts with keys: project_num, title, fiscal_year, pi_names, abstract.
    """
    payload = {
        "criteria": {"advanced_text_search": {"operator": "and", "search_field": "all", "search_text": keywords}},
        "offset": 0,
        "limit": limit,
        "sort_field": "fiscal_year",
        "sort_order": "desc",
    }

    try:
        resp = requests.post(NIH_REPORTER_URL, json=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        logger.error("NIH RePORTER API error: %s", exc)
        return []

    results = []
    for proj in data.get("results", []):
        pis = [p.get("full_name", "") for p in proj.get("principal_investigators", [])]
        results.append(
            {
                "project_num": proj.get("project_num", ""),
                "title": proj.get("project_title", ""),
                "fiscal_year": proj.get("fiscal_year", ""),
                "pi_names": ", ".join(pis),
                "total_cost": proj.get("total_cost", 0),
                "abstract": (proj.get("abstract_text", "") or "")[:500],
            }
        )

    logger.info("NIH RePORTER: %d results for '%s'", len(results), keywords)
    return results


def draft_narrative(
    opportunity: dict,
    project_info: dict,
    model: Optional[str] = None,
) -> str:
    """
    Draft a Project Narrative / Specific Aims page using GPT-4.

    Args:
        opportunity:  dict from discover_grants() or manually constructed
        project_info: dict with keys: title, hypothesis, approach, innovation,
                      team, preliminary_data
        model:        override model (defaults to settings.openai_model)

    Returns:
        Formatted narrative as a string (Markdown).
    """
    user_prompt = (
        f"Funding Opportunity: {opportunity.get('title', 'N/A')}\n"
        f"Agency: {opportunity.get('agency', 'N/A')}\n"
        f"Award Ceiling: {opportunity.get('award_ceiling', 'N/A')}\n\n"
        f"Project Title: {project_info.get('title', '')}\n"
        f"Central Hypothesis: {project_info.get('hypothesis', '')}\n"
        f"Approach / Methods: {project_info.get('approach', '')}\n"
        f"Innovation: {project_info.get('innovation', '')}\n"
        f"Team: {project_info.get('team', '')}\n"
        f"Preliminary Data: {project_info.get('preliminary_data', '')}\n"
    )

    response = _client.chat.completions.create(
        model=model or settings.openai_model,
        messages=[
            {"role": "system", "content": _NARRATIVE_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.4,
        max_tokens=1200,
    )

    narrative = response.choices[0].message.content.strip()
    logger.info("Drafted narrative for opportunity '%s'", opportunity.get("title", ""))
    return narrative


def save_application(
    narrative: str,
    opportunity: dict,
    output_dir: str = "output/grants",
) -> Path:
    """
    Save the drafted narrative to a Markdown file.

    Returns:
        Path to the saved file.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    opp_id = opportunity.get("opportunity_id", "unknown").replace("/", "-")
    file_path = out / f"narrative_{opp_id}.md"

    header = (
        f"# Grant Application Draft\n\n"
        f"**Opportunity:** {opportunity.get('title', '')}\n"
        f"**Agency:** {opportunity.get('agency', '')}\n"
        f"**Close Date:** {opportunity.get('close_date', '')}\n"
        f"**URL:** {opportunity.get('url', '')}\n\n"
        f"---\n\n"
    )

    file_path.write_text(header + narrative, encoding="utf-8")
    logger.info("Saved grant narrative to %s", file_path)
    return file_path
