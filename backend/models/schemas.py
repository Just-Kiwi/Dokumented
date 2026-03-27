"""
Pydantic request/response schemas for FastAPI.
"""
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime


# Config schemas
class ConfigUpdate(BaseModel):
    """Update configuration (API keys, settings)."""
    key: str
    value: str


class ConfigResponse(BaseModel):
    """Configuration response."""
    key: str
    value: str
    updated_at: datetime

    class Config:
        from_attributes = True


# Schema definition schemas
class FieldDefinition(BaseModel):
    """Definition of a field to extract."""
    name: str
    description: Optional[str] = None
    required: bool = True


class SchemaRequest(BaseModel):
    """Request to set extraction schema."""
    fields: List[FieldDefinition]


# Extraction schemas
class ExtractRequest(BaseModel):
    """Request to extract fields from document."""
    filename: str
    raw_text: str
    schema: Optional[List[FieldDefinition]] = None


class FieldStatus(BaseModel):
    """Status of a single field."""
    status: str  # 'filled', 'missing', 'uncertain'
    value: Optional[Any] = None
    confidence: float


class dLLMReport(BaseModel):
    """Report from dLLM field check."""
    fields: Dict[str, FieldStatus]


class ExtractionReportResponse(BaseModel):
    """Report on extraction result."""
    result_id: int
    filename: str
    script_id: Optional[int] = None
    script_version: int
    status: str
    extracted_json: Dict[str, Any]
    missing_fields: List[str]
    dllm_report: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


# Human override schemas
class HumanOverride(BaseModel):
    """Human override for a field."""
    field_name: str
    value: Optional[Any] = None  # None means null/missing


class HumanOverridesRequest(BaseModel):
    """Request to apply human overrides."""
    result_id: int
    overrides: List[HumanOverride]


# WebSocket schemas
class WSEvent(BaseModel):
    """WebSocket event sent to client."""
    event: str
    data: Optional[Dict[str, Any]] = None


# Credit check schemas
class CreditCheckStatus(BaseModel):
    """Status of a single API's credits."""
    provider: str
    configured: bool
    has_credits: bool
    error: Optional[str] = None


class CreditCheckResponse(BaseModel):
    """Response from credit check endpoint."""
    anthropic: CreditCheckStatus
    mercury: CreditCheckStatus
