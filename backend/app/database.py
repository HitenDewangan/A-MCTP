import uuid
from datetime import datetime

from sqlalchemy import create_engine, Column, String, Float, DateTime, Text, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

from .config import settings

connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def _uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=_uuid)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    jobs = relationship("TranslationJob", back_populates="owner", cascade="all, delete-orphan")


class TranslationJob(Base):
    """
    Represents one batch (file-upload) or streaming decode job, and its
    result -- backs Feature Set 1's Translation History Dashboard.
    """
    __tablename__ = "translation_jobs"

    id = Column(String, primary_key=True, default=_uuid)  # == Celery job_id
    owner_id = Column(String, ForeignKey("users.id"), nullable=True)  # nullable: anon sessions allowed
    session_id = Column(String, nullable=True, index=True)  # for anonymous users

    source_type = Column(String, nullable=False)  # "upload" | "stream"
    original_filename = Column(String, nullable=True)
    status = Column(String, default="QUEUED")  # QUEUED | PROCESSING | DONE | FAILED

    decoded_text = Column(Text, nullable=True)
    symbol_stream = Column(Text, nullable=True)
    wpm_estimate = Column(Float, nullable=True)
    warning = Column(Text, nullable=True)
    error = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    owner = relationship("User", back_populates="jobs")


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
