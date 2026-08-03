"""HTTP endpoints for generating and retrieving schedule versions."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from src.scheduling.explain import generate_schedule_explanation
from src.scheduling.schemas import ScheduleExplanation

from src.auth.dependencies import get_current_user_id
from src.db.session import get_db
from src.scheduling.persistence import (
    get_current_schedule,
    get_schedule_history,
    get_schedule_version,
    persist_schedule,
)
from src.scheduling.schemas import ScheduleRequest, ScheduleVersion
from src.scheduling.service import build_schedule

router = APIRouter(prefix="/schedules", tags=["schedules"])


@router.post("", response_model=ScheduleVersion, status_code=status.HTTP_201_CREATED)
def create_schedule(
    request: ScheduleRequest,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> ScheduleVersion:
    """Generate and persist a new, immutable schedule version."""
    return persist_schedule(db, user_id, build_schedule(request))


@router.get("/current", response_model=ScheduleVersion)
def read_current_schedule(
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> ScheduleVersion:
    schedule = get_current_schedule(db, user_id)
    if schedule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No schedule found")
    return schedule


@router.get("/history", response_model=list[ScheduleVersion])
def read_schedule_history(
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> list[ScheduleVersion]:
    return get_schedule_history(db, user_id)


@router.get("/{version_id}", response_model=ScheduleVersion)
def read_schedule_version(
    version_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> ScheduleVersion:
    schedule = get_schedule_version(db, user_id, version_id)
    if schedule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule version not found")
    return schedule
@router.get("/current/explain", response_model=ScheduleExplanation)
def explain_current_schedule(
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> ScheduleExplanation:
    """Explain why the current schedule is ordered the way it is (P4-SRE8)."""
    schedule = get_current_schedule(db, user_id)
    if schedule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No schedule found")

    try:
        message = generate_schedule_explanation(schedule.plan)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return ScheduleExplanation(message=message)


@router.get("/{version_id}/explain", response_model=ScheduleExplanation)
def explain_schedule_version(
    version_id: uuid.UUID,
    db: Session = Depends(get_db),
    user_id: uuid.UUID = Depends(get_current_user_id),
) -> ScheduleExplanation:
    """Explain why a specific schedule version is ordered the way it is (P4-SRE8)."""
    schedule = get_schedule_version(db, user_id, version_id)
    if schedule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Schedule version not found")

    try:
        message = generate_schedule_explanation(schedule.plan)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return ScheduleExplanation(message=message)