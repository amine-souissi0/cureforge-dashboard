import logging
from typing import Optional

from jinja2 import Template
from openai import OpenAI

from config.settings import settings

logger = logging.getLogger(__name__)

_client = OpenAI(api_key=settings.openai_api_key)

# Default base template — Jinja2 variables are filled by GPT-4 with context
DEFAULT_TEMPLATE = """
<p>Hi {{ name }},</p>

<p>
I'm reaching out because {{ firm }} has a strong track record investing in
{{ focus_area }}, and I believe our work at
<strong>LongevityInTime</strong> aligns closely with your thesis.
</p>

<p>
LongevityInTime is building an AI-driven platform to accelerate longevity
research — from hypothesis generation to clinical trial design — powered by
the CureForge knowledge graph. {{ personalized_hook }}
</p>

<p>
Would you be open to a 20-minute call this week or next?
</p>

<p>
Best regards,<br/>
The LongevityInTime Team
</p>
""".strip()

_SYSTEM_PROMPT = """\
You are an expert startup fundraising copywriter.
Given an investor's profile, write a single short paragraph (2–3 sentences)
called the "personalized hook" that:
  1. References something specific about their focus area or background.
  2. Explains concisely why LongevityInTime is a natural fit for them.
  3. Sounds warm, direct, and human — not salesy.
Return only the paragraph text, no extra explanation.\
"""


def personalize(investor: dict, template: Optional[str] = None) -> str:
    """
    Render a personalized HTML email body for a given investor.

    Args:
        investor: dict with keys: name, email, firm, focus_area, notes
        template: optional Jinja2 HTML template string; uses DEFAULT_TEMPLATE if None

    Returns:
        Rendered HTML string ready to be sent.
    """
    base = template or DEFAULT_TEMPLATE

    user_prompt = (
        f"Investor name: {investor.get('name', '')}\n"
        f"Firm: {investor.get('firm', '')}\n"
        f"Focus area: {investor.get('focus_area', '')}\n"
        f"Additional notes: {investor.get('notes', '')}\n"
    )

    response = _client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
        max_tokens=200,
    )

    hook = response.choices[0].message.content.strip()
    logger.debug("Generated hook for %s: %s", investor.get("email"), hook)

    rendered = Template(base).render(
        name=investor.get("name", ""),
        firm=investor.get("firm", ""),
        focus_area=investor.get("focus_area", ""),
        personalized_hook=hook,
    )
    return rendered


def default_subject(investor: dict) -> str:
    """Return a personalized email subject line for the investor."""
    return (
        f"LongevityInTime × {investor.get('firm', 'Your Fund')} — "
        "Partnering to Extend Healthy Human Lifespan"
    )
