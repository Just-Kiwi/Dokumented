"""
SQLAlchemy ORM models for DocFlow database.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, ForeignKey, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from db.database import Base


class StatusEnum(str, enum.Enum):
    """Status enum for extraction results."""
    complete = "complete"
    partial = "partial"
    failed = "failed"


class OutcomeEnum(str, enum.Enum):
    """Outcome enum for retry log."""
    resolved = "resolved"
    escalated = "escalated"
    new_fingerprint = "new_fingerprint"


class ScriptLibrary(Base):
    """One row per discovered document format variant."""
    __tablename__ = "script_library"

    id = Column(Integer, primary_key=True, index=True)
    fingerprint = Column(String, unique=True, index=True, nullable=False)
    script_body = Column(Text, nullable=False)
    version = Column(Integer, default=1)
    success_count = Column(Integer, default=0)
    fail_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    extraction_results = relationship("ExtractionResult", back_populates="script")


class ExtractionResult(Base):
    """One row per document processed."""
    __tablename__ = "extraction_results"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    fingerprint = Column(String, ForeignKey("script_library.fingerprint"), nullable=False)
    script_version = Column(Integer, nullable=False)
    raw_text = Column(Text, nullable=False)
    extracted_json = Column(JSON, nullable=False)
    human_overrides = Column(JSON, default={})
    status = Column(Enum(StatusEnum), default=StatusEnum.complete)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    script = relationship("ScriptLibrary", back_populates="extraction_results")
    retry_logs = relationship("RetryLog", back_populates="extraction_result")


class RetryLog(Base):
    """One row per retry attempt."""
    __tablename__ = "retry_log"

    id = Column(Integer, primary_key=True, index=True)
    result_id = Column(Integer, ForeignKey("extraction_results.id"), nullable=False)
    attempt_number = Column(Integer, nullable=False)
    missing_fields = Column(JSON, default=[])
    dllm_report = Column(JSON, nullable=False)
    script_before = Column(Text, nullable=False)
    script_after = Column(Text)
    outcome = Column(Enum(OutcomeEnum), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    extraction_result = relationship("ExtractionResult", back_populates="retry_logs")


class AppConfig(Base):
    """Application configuration (API keys, settings)."""
    __tablename__ = "app_config"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True, nullable=False)
    value = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
