import json
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Enum
from sqlalchemy.orm import Session
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config.settings import settings


class ReplyStatus(str, PyEnum):
    pending = "pending"
    interested = "interested"
    not_interested = "not_interested"
    needs_info = "needs_info"
    other = "other"


class Base(DeclarativeBase):
    pass


class AgentSession(Base):
    """
    Generic JSON payload storage for multi-step agent runs (orchestrator, grant workflow, etc.).
    Not a vector store — use external RAG only when retrieval requirements justify it.
    """

    __tablename__ = "agent_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(128), nullable=False, unique=True, index=True)
    task_type = Column(String(128), nullable=False, index=True)
    payload_json = Column(Text, nullable=False)
    result_json = Column(Text, nullable=True)
    status = Column(String(32), nullable=False, default="pending")
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<AgentSession id={self.id} session_id={self.session_id!r} task={self.task_type!r}>"


class OutreachRecord(Base):
    __tablename__ = "outreach_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False, unique=True, index=True)
    firm = Column(String(255), nullable=True)
    focus_area = Column(String(512), nullable=True)
    sent_at = Column(DateTime, nullable=True)
    message_id = Column(String(512), nullable=True)
    reply_status = Column(
        Enum(ReplyStatus),
        default=ReplyStatus.pending,
        nullable=False,
    )
    reply_received_at = Column(DateTime, nullable=True)
    raw_reply = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return (
            f"<OutreachRecord id={self.id} email={self.email!r} "
            f"status={self.reply_status}>"
        )


engine = create_engine(
    settings.db_url,
    connect_args={"check_same_thread": False} if "sqlite" in settings.db_url else {},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    """Create all tables if they don't exist yet."""
    Base.metadata.create_all(bind=engine)


def upsert_agent_session_row(
    db: Session,
    *,
    session_id: str,
    task_type: str,
    payload: dict,
    result: dict | None = None,
    status: str = "pending",
    error_message: str | None = None,
) -> AgentSession:
    """Insert or update an AgentSession by public session_id."""
    row = db.query(AgentSession).filter_by(session_id=session_id).first()
    payload_s = json.dumps(payload, default=str)
    result_s = json.dumps(result, default=str) if result is not None else None
    now = datetime.utcnow()
    if row is None:
        row = AgentSession(
            session_id=session_id,
            task_type=task_type,
            payload_json=payload_s,
            result_json=result_s,
            status=status,
            error_message=error_message,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
    else:
        row.task_type = task_type
        row.payload_json = payload_s
        if result_s is not None:
            row.result_json = result_s
        row.status = status
        row.error_message = error_message
        row.updated_at = now
    return row


def get_session():
    """Yield a database session and close it after use."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
