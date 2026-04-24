"""
FastAPI webhook server.

Receives inbound email events from Resend, parses the reply intent via GPT-4,
and updates the OutreachRecord in the database.

Optional JSON logging: set USE_JSON_LOGGING=1
Optional task API protection: set WEBHOOK_API_KEY and send header X-Webhook-Api-Key
(Resend inbound webhooks do not use WEBHOOK_API_KEY — only /tasks and /tasks/{id}.)

Run with:
    uvicorn webhook.server:app --host 0.0.0.0 --port 8000
"""

import hashlib
import hmac
import logging
from datetime import datetime

from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request, status

from agents.intent_parser import parse_intent
from config.settings import settings
from core.logging_config import configure_json_logging
from models.database import OutreachRecord, SessionLocal, init_db
from . import tasks as task_jobs

logger = logging.getLogger(__name__)


def _require_tasks_api_key(x_webhook_api_key: str | None) -> None:
    expected = (settings.webhook_api_key or "").strip()
    if not expected:
        return
    if not x_webhook_api_key or x_webhook_api_key.strip() != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Webhook-Api-Key.",
        )


@asynccontextmanager
async def lifespan(application: FastAPI):
    if settings.use_json_logging:
        configure_json_logging()
    init_db()
    yield


app = FastAPI(title="Communication Agent Webhook", version="1.0.0", lifespan=lifespan)


def _verify_signature(payload: bytes, signature: str) -> bool:
    """
    Validate the Resend webhook HMAC-SHA256 signature.

    Resend sends the signature as: sha256=<hex_digest>
    """
    if not settings.webhook_secret:
        logger.warning("WEBHOOK_SECRET not configured — skipping signature check.")
        return True

    expected = (
        "sha256="
        + hmac.new(
            settings.webhook_secret.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()
    )
    return hmac.compare_digest(expected, signature)


@app.post("/webhook", status_code=status.HTTP_200_OK)
async def handle_webhook(
    request: Request,
    svix_signature: str = Header(default="", alias="svix-signature"),
    resend_signature: str = Header(default="", alias="resend-signature"),
) -> dict:
    """
    Receive an inbound email event from Resend.

    Expected JSON body (Resend inbound email payload):
    {
        "type": "email.received",
        "data": {
            "from": "investor@example.com",
            "text": "...",
            "html": "..."
        }
    }
    """
    raw_body = await request.body()

    # Accept either Resend's own signature header or Svix (used by some plans)
    sig_header = resend_signature or svix_signature
    if sig_header and not _verify_signature(raw_body, sig_header):
        logger.warning("Webhook signature verification failed.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature.",
        )

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Request body is not valid JSON.",
        )

    event_type = payload.get("type", "")
    if event_type != "email.received":
        # Acknowledge other event types without processing
        logger.debug("Ignoring event type: %s", event_type)
        return {"status": "ignored", "type": event_type}

    data = payload.get("data", {})
    sender_email: str = data.get("from", "").lower().strip()
    # Prefer plain text for intent parsing; fall back to html
    body_text: str = data.get("text") or data.get("html") or ""

    if not sender_email or not body_text:
        logger.warning("Webhook payload missing sender or body: %s", data)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Missing 'from' or email body in payload.",
        )

    intent = parse_intent(body_text)
    logger.info(
        "Inbound reply processed",
        extra={"sender": sender_email, "intent": intent.value},
    )

    db = SessionLocal()
    try:
        record = db.query(OutreachRecord).filter_by(email=sender_email).first()
        if record:
            record.reply_status = intent
            record.reply_received_at = datetime.utcnow()
            record.raw_reply = body_text[:4000]  # guard against huge bodies
            db.commit()
            logger.info("Updated OutreachRecord for %s", sender_email)
        else:
            logger.warning(
                "Received reply from unknown sender: %s — no matching record.",
                sender_email,
            )
    finally:
        db.close()

    return {"status": "ok", "intent": intent.value}


@app.post("/tasks", status_code=status.HTTP_202_ACCEPTED)
async def submit_task(
    background_tasks: BackgroundTasks,
    request: Request,
    x_webhook_api_key: str | None = Header(default=None, alias="X-Webhook-Api-Key"),
) -> dict:
    """
    Enqueue a synchronous dispatch job (runs in-process after response).

    Body: {"task_type": "grant.discover", "payload": {"keywords": "aging", "limit": 5}}
    """
    _require_tasks_api_key(x_webhook_api_key)
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Request body is not valid JSON.",
        )
    task_type = body.get("task_type")
    payload = body.get("payload") if isinstance(body.get("payload"), dict) else {}
    if not task_type or not isinstance(task_type, str):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Missing string 'task_type'.",
        )

    task_id = task_jobs.enqueue(
        task_type,
        payload,
        SessionLocal,
        background_tasks.add_task,
    )
    logger.info("Task accepted", extra={"task_id": task_id, "task_type": task_type})
    return {"task_id": task_id, "status": "queued"}


@app.get("/tasks/{task_id}")
async def task_status(
    task_id: str,
    x_webhook_api_key: str | None = Header(default=None, alias="X-Webhook-Api-Key"),
) -> dict:
    """Poll task status populated by the in-memory store."""
    _require_tasks_api_key(x_webhook_api_key)
    snap = task_jobs.get_snapshot(task_id)
    if snap is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown task_id.")
    return {"task_id": task_id, **snap}


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
