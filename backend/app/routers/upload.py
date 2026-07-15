import asyncio
import json
import os
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..auth import get_current_user_optional
from ..celery_app import celery_app
from ..config import settings
from ..database import TranslationJob, User, get_db
from ..models import JobResultResponse, JobSubmitResponse, SymbolEventOut
from ..tasks import decode_upload_task

router = APIRouter(prefix="/api/v1/decode", tags=["decode"])


@router.post("/upload", response_model=JobSubmitResponse)
async def upload_audio(
    request: Request,
    file: UploadFile = File(...),
    low_hz: float = Form(default=None),
    high_hz: float = Form(default=None),
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type '{ext}'. Allowed: {sorted(settings.ALLOWED_EXTENSIONS)}")

    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)
    if size_mb > settings.MAX_UPLOAD_MB:
        raise HTTPException(400, f"File too large ({size_mb:.1f}MB). Max is {settings.MAX_UPLOAD_MB}MB.")

    job_id = str(uuid.uuid4())
    saved_path = os.path.join(settings.UPLOAD_DIR, f"{job_id}{ext}")
    with open(saved_path, "wb") as f:
        f.write(contents)

    session_id = request.headers.get("X-Session-Id")
    job = TranslationJob(
        id=job_id,
        owner_id=user.id if user else None,
        session_id=None if user else session_id,
        source_type="upload",
        original_filename=file.filename,
        status="QUEUED",
    )
    db.add(job)
    db.commit()

    decode_upload_task.apply_async(
        args=[
            job_id,
            saved_path,
            low_hz if low_hz is not None else settings.DEFAULT_LOW_HZ,
            high_hz if high_hz is not None else settings.DEFAULT_HIGH_HZ,
        ],
        task_id=job_id,
    )

    estimated_seconds = round(max(1.5, size_mb * 1.2), 1)
    return JobSubmitResponse(job_id=job_id, status="QUEUED", estimated_processing_seconds=estimated_seconds)


@router.get("/status/{job_id}/stream")
async def stream_status(job_id: str):
    """Server-Sent Events endpoint streaming Celery task progress (PRD 4.2)."""

    async def event_generator():
        last_payload = None
        while True:
            result = celery_app.AsyncResult(job_id)
            info = result.info if isinstance(result.info, dict) else {}
            payload = {
                "job_id": job_id,
                "state": result.state,
                "progress": info.get("progress"),
                "stage": info.get("stage"),
            }
            if payload != last_payload:
                yield f"data: {json.dumps(payload)}\n\n"
                last_payload = payload
            if result.state in ("SUCCESS", "FAILURE"):
                break
            await asyncio.sleep(0.6)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/result/{job_id}", response_model=JobResultResponse)
def get_result(job_id: str, db: Session = Depends(get_db)):
    job = db.query(TranslationJob).filter(TranslationJob.id == job_id).first()
    if not job:
        raise HTTPException(404, "Job not found")
    return JobResultResponse(
        job_id=job.id,
        status=job.status,
        decoded_text=job.decoded_text,
        symbol_stream=job.symbol_stream,
        wpm_estimate=job.wpm_estimate,
        warning=job.warning,
        error=job.error,
        original_filename=job.original_filename,
        created_at=job.created_at,
    )
