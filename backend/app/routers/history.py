from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import get_current_user_required
from ..database import TranslationJob, User, get_db
from ..models import HistoryItem

router = APIRouter(prefix="/api/v1/history", tags=["history"])


@router.get("", response_model=List[HistoryItem])
def get_history(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_required),
    limit: int = 50,
):
    jobs = (
        db.query(TranslationJob)
        .filter(TranslationJob.owner_id == user.id)
        .order_by(TranslationJob.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        HistoryItem(
            job_id=j.id,
            source_type=j.source_type,
            original_filename=j.original_filename,
            status=j.status,
            decoded_text=j.decoded_text,
            wpm_estimate=j.wpm_estimate,
            created_at=j.created_at,
        )
        for j in jobs
    ]
