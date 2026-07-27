from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# --- Auth ---
class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=6, max_length=128)


class UserLogin(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ProfileUpdate(BaseModel):
    display_name: Optional[str] = Field(default=None, max_length=48)
    callsign: Optional[str] = Field(default=None, max_length=24)
    bio: Optional[str] = Field(default=None, max_length=280)
    preferred_wpm: float = Field(default=20.0, ge=5, le=60)
    low_hz: float = Field(default=700.0, ge=100, le=3000)
    high_hz: float = Field(default=800.0, ge=100, le=3000)


class ProfileOut(ProfileUpdate):
    username: str
    joined_at: datetime


# --- Jobs ---
class JobSubmitResponse(BaseModel):
    job_id: str
    status: str
    estimated_processing_seconds: float


class SymbolEventOut(BaseModel):
    kind: str
    start_s: float
    end_s: float


class JobResultResponse(BaseModel):
    job_id: str
    status: str
    decoded_text: Optional[str] = None
    symbol_stream: Optional[str] = None
    wpm_estimate: Optional[float] = None
    detected_freq_hz: Optional[float] = None
    warning: Optional[str] = None
    error: Optional[str] = None
    events: Optional[List[SymbolEventOut]] = None
    original_filename: Optional[str] = None
    created_at: Optional[datetime] = None


class HistoryItem(BaseModel):
    job_id: str
    source_type: str
    original_filename: Optional[str]
    status: str
    decoded_text: Optional[str]
    wpm_estimate: Optional[float]
    created_at: datetime

    class Config:
        from_attributes = True


# --- Synthesis ---
class SynthesizeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    wpm: float = Field(default=20.0, ge=5, le=60)
    freq_hz: float = Field(default=750.0, ge=300, le=1200)
