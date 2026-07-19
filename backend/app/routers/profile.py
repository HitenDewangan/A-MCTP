from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import get_current_user_required
from ..database import User, UserProfile, get_db
from ..models import ProfileOut, ProfileUpdate

router = APIRouter(prefix="/api/v1/profile", tags=["profile"])


def profile_out(user: User, profile: UserProfile | None) -> ProfileOut:
    return ProfileOut(
        username=user.username,
        joined_at=user.created_at,
        display_name=profile.display_name if profile else user.username,
        callsign=profile.callsign if profile else "",
        bio=profile.bio if profile else "",
        preferred_wpm=profile.preferred_wpm if profile else 20.0,
        low_hz=profile.low_hz if profile else 700.0,
        high_hz=profile.high_hz if profile else 800.0,
    )


@router.get("", response_model=ProfileOut)
def get_profile(user: User = Depends(get_current_user_required)):
    return profile_out(user, user.profile)


@router.put("", response_model=ProfileOut)
def update_profile(
    payload: ProfileUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user_required),
):
    profile = user.profile or UserProfile(user_id=user.id)
    profile.display_name = payload.display_name.strip() if payload.display_name else user.username
    profile.callsign = payload.callsign.strip().upper() if payload.callsign else ""
    profile.bio = payload.bio.strip() if payload.bio else ""
    profile.preferred_wpm = payload.preferred_wpm
    profile.low_hz = payload.low_hz
    profile.high_hz = payload.high_hz
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile_out(user, profile)
