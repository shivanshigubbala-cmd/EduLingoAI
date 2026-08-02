"""Schedule persistence and immutable version retrieval — P4-SHI8."""

import json
import uuid

from sqlalchemy.orm import Session

from src.db.models import Session as UserSession
from src.db.models import SessionType
from src.scheduling.schemas import SchedulePlan, ScheduleVersion


def _as_user_id(user_id: uuid.UUID | str) -> uuid.UUID:
    return uuid.UUID(str(user_id)) if isinstance(user_id, str) else user_id


def _to_version(session: UserSession) -> ScheduleVersion:
    """Deserialize one schedule session into its public version record."""
    return ScheduleVersion(
        version_id=session.id,
        created_at=session.started_at,
        plan=SchedulePlan.model_validate(json.loads(session.summary or "{}")),
    )


def persist_schedule(
    db: Session,
    user_id: uuid.UUID | str,
    plan: SchedulePlan,
) -> ScheduleVersion:
    """Save a new immutable schedule version without modifying prior versions."""
    row = UserSession(
        user_id=_as_user_id(user_id),
        type=SessionType.schedule,
        summary=json.dumps(plan.model_dump(mode="json")),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_version(row)


def get_current_schedule(
    db: Session,
    user_id: uuid.UUID | str,
) -> ScheduleVersion | None:
    """Return the newest saved schedule version for a user."""
    row = (
        db.query(UserSession)
        .filter(
            UserSession.user_id == _as_user_id(user_id),
            UserSession.type == SessionType.schedule,
        )
        .order_by(UserSession.started_at.desc(), UserSession.id.desc())
        .first()
    )
    return _to_version(row) if row is not None else None


def get_schedule_history(
    db: Session,
    user_id: uuid.UUID | str,
) -> list[ScheduleVersion]:
    """Return every saved schedule version, newest first."""
    rows = (
        db.query(UserSession)
        .filter(
            UserSession.user_id == _as_user_id(user_id),
            UserSession.type == SessionType.schedule,
        )
        .order_by(UserSession.started_at.desc(), UserSession.id.desc())
        .all()
    )
    return [_to_version(row) for row in rows]


def get_schedule_version(
    db: Session,
    user_id: uuid.UUID | str,
    version_id: uuid.UUID | str,
) -> ScheduleVersion | None:
    """Return one schedule version owned by the requested user."""
    version_uuid = uuid.UUID(str(version_id)) if isinstance(version_id, str) else version_id
    row = (
        db.query(UserSession)
        .filter(
            UserSession.id == version_uuid,
            UserSession.user_id == _as_user_id(user_id),
            UserSession.type == SessionType.schedule,
        )
        .one_or_none()
    )
    return _to_version(row) if row is not None else None
