from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Enum
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


def get_session():
    """Yield a database session and close it after use."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
