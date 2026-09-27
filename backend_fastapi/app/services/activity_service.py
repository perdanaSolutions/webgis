from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.audit import UserActivity
from app.models.auth import User
from app.schemas.activity_log import ActivityLogResponse
from app.utils.pagination import page_response


def log_activity(
    db: Session,
    *,
    user_id: UUID | None,
    action: str,
    resource: str,
    status: str = "SUCCESS",
    detail: dict | None = None,
    record_id: str | None = None,
    ip_address: str | None = None,
    commit: bool = True,
) -> None:
    db.add(UserActivity(
        user_id=user_id, action=action, resource=resource, status=status,
        detail=detail, record_id=record_id, ip_address=ip_address,
    ))
    if commit:
        db.commit()


def list_logs(db: Session, search: str | None, status_filter: str | None, page: int, limit: int) -> dict:
    query = select(UserActivity).outerjoin(User, UserActivity.user_id == User.id)
    if search:
        pattern = f"%{search}%"
        query = query.where(or_(
            UserActivity.action.ilike(pattern),
            UserActivity.resource.ilike(pattern),
            User.full_name.ilike(pattern),
            User.username.ilike(pattern),
        ))
    if status_filter:
        query = query.where(UserActivity.status == status_filter.upper())

    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(
        query.order_by(UserActivity.created_at.desc(), UserActivity.id.desc()).offset((page - 1) * limit).limit(limit)
    ).unique().all()
    return page_response(total, page, limit, [ActivityLogResponse.model_validate(r) for r in rows])
