# Communication Agent System

Autonomous investor outreach agent for **LongevityInTime.org** — sends personalized emails via Resend, receives replies through a webhook, classifies intent with GPT-4, and displays a live Streamlit dashboard.

---

## Quick Start

### 1. Set up environment

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in your keys
```

### 2. Configure `.env`

| Variable | Description |
|---|---|
| `RESEND_API_KEY` | From [resend.com/api-keys](https://resend.com/api-keys) |
| `OPENAI_API_KEY` | Your OpenAI key |
| `WEBHOOK_SECRET` | Secret set in Resend webhook settings |
| `FROM_EMAIL` | Verified sender (e.g. `outreach@longevityintime.org`) |
| `DB_URL` | SQLite path (default: `sqlite:///./outreach.db`) |

### 3. Domain Setup (LongevityInTime.org)

In Resend → Domains, add `longevityintime.org` and copy the provided **DKIM** and **SPF** DNS records into your DNS provider. Resend will verify automatically.

### 4. Run investor outreach

```bash
# Dry run — preview without sending
python -m scripts.run_outreach --csv data/investors_sample.csv --dry-run

# Send live emails
python -m scripts.run_outreach --csv data/investors.csv
```

CSV must have columns: `name, email, firm, focus_area` (and optionally `notes`).

### 5. Start the webhook server

```bash
uvicorn webhook.server:app --host 0.0.0.0 --port 8000
```

Configure Resend → Webhooks to POST to `https://<your-domain>/webhook` with event `email.received`.

### 6. Open the dashboard

```bash
streamlit run dashboard/app.py
```

---

## Project Structure

```
communication-agent/
├── config/settings.py          # Pydantic settings (loads .env)
├── agents/
│   ├── email_agent.py          # Resend API wrapper
│   ├── personalization.py      # GPT-4 email personalization
│   └── intent_parser.py        # GPT-4 reply intent classifier
├── models/database.py          # SQLAlchemy ORM + SQLite
├── webhook/server.py           # FastAPI inbound webhook
├── dashboard/app.py            # Streamlit status board
├── scripts/run_outreach.py     # CLI outreach runner
├── tests/                      # 29 pytest tests (fully mocked)
└── data/investors_sample.csv   # Sample investor CSV
```

## Running Tests

```bash
pytest tests/ -v
```

All 29 tests use mocked Resend and OpenAI calls — no API keys required.

---

## Roadmap

| Agent | Description |
|---|---|
| Grant Agent | NIH/NSF RFP parsing, SF424 auto-fill, grants.gov submission |
| Dataset Request Agent | DUA/data access letter drafting and tracking |
| Preprint Agent | bioRxiv/medRxiv/arXiv submission via API |
| Journal Submission Agent | Editorial Manager / ScholarOne integration |
| Patent Agent | USPTO provisional patent XML + Patent Center API |
| FDA Agent | IND/NDA eCTD package assembly + FDA ESG submission |

Each future agent follows the pattern: `agents/<name>_agent.py` + `tests/test_<name>_agent.py`.
