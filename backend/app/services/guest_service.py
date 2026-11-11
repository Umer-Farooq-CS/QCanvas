"""
Private guest ("Try demo") accounts.

Previously every visitor who clicked "Try demo" logged into ONE shared
account (demo@qcanvas.dev), so everyone saw, overwrote and deleted each
other's files, and "demo data cleared on logout" was never implemented
server-side. Now each click creates an isolated, temporary guest user:

- random credentials that are never revealed (guests can't log in by password);
- workspace data is purged on logout, or after GUEST_ACCOUNT_TTL_HOURS;
- expired guests are purged opportunistically whenever a new guest is created,
  so no scheduler is needed.
"""
from __future__ import annotations

import logging
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.config.settings import settings
from app.models.database_models import (
    Conversion,
    File,
    Folder,
    Job,
    Project,
    Simulation,
    User,
    UserRole,
)

logger = logging.getLogger(__name__)

GUEST_EMAIL_DOMAIN = "guest.qcanvas.invalid"  # .invalid is reserved: never deliverable
LEGACY_SHARED_DEMO_EMAIL = "demo@qcanvas.dev"


def guest_expiry(user: User) -> Optional[datetime]:
    if user.role != UserRole.DEMO or not user.created_at:
        return None
    return user.created_at + timedelta(hours=settings.GUEST_ACCOUNT_TTL_HOURS)


def is_expired_guest(user: User) -> bool:
    expiry = guest_expiry(user)
    return expiry is not None and datetime.utcnow() >= expiry


def active_guest_count(db: Session) -> int:
    """Live (not deleted, not expired) guest accounts, for the global cap."""
    cutoff = datetime.utcnow() - timedelta(hours=settings.GUEST_ACCOUNT_TTL_HOURS)
    return (
        db.query(User)
        .filter(
            User.role == UserRole.DEMO,
            User.deleted_at == None,  # noqa: E711
            User.created_at >= cutoff,
        )
        .count()
    )


def create_guest(db: Session) -> User:
    suffix = secrets.token_hex(4)
    guest = User(
        id=uuid.uuid4(),
        email=f"guest-{secrets.token_hex(8)}@{GUEST_EMAIL_DOMAIN}",
        username=f"guest_{suffix}",
        full_name=f"Guest {suffix.upper()}",
        role=UserRole.DEMO,
        is_active=True,
        is_verified=True,
    )
    # Random throwaway password: guests authenticate only via their issued token.
    guest.set_password(secrets.token_urlsafe(32))
    guest.last_login_at = datetime.utcnow()
    db.add(guest)
    db.commit()
    db.refresh(guest)
    return guest


def purge_guest(db: Session, user: User) -> None:
    """Delete a guest's workspace and deactivate the account (no commit)."""
    if user.role != UserRole.DEMO:
        raise ValueError("purge_guest called on a non-guest account")
    uid = user.id
    # Order matters: files reference folders/projects; folders reference projects.
    db.query(File).filter(File.user_id == uid).delete(synchronize_session=False)
    db.query(Folder).filter(Folder.user_id == uid).delete(synchronize_session=False)
    db.query(Job).filter(Job.user_id == uid).delete(synchronize_session=False)
    db.query(Project).filter(Project.user_id == uid).delete(synchronize_session=False)
    db.query(Simulation).filter(Simulation.user_id == uid).delete(synchronize_session=False)
    db.query(Conversion).filter(Conversion.user_id == uid).delete(synchronize_session=False)
    try:
        from app.models.gamification import (
            GamificationActivity,
            UserAchievement,
            UserGamification,
        )

        db.query(GamificationActivity).filter(GamificationActivity.user_id == uid).delete(synchronize_session=False)
        db.query(UserAchievement).filter(UserAchievement.user_id == uid).delete(synchronize_session=False)
        db.query(UserGamification).filter(UserGamification.user_id == uid).delete(synchronize_session=False)
    except Exception:  # gamification tables optional in some deployments
        logger.exception("Failed to purge guest gamification rows")
        raise
    # Soft-delete the user row (keeps audit/shared-snippet references valid)
    # and invalidate every token issued to it.
    user.is_active = False
    user.deleted_at = datetime.utcnow()
    user.token_version = (user.token_version or 0) + 1


GUEST_ACTIVITY_WRITE_INTERVAL = timedelta(minutes=15)


def touch_guest(db: Session, user: User, force: bool = False) -> None:
    """
    Record guest activity. Called on every authenticated request (throttled to
    one DB write per 15 minutes) and on token refresh.
    """
    if user.role != UserRole.DEMO:
        return
    now = datetime.utcnow()
    last = user.last_login_at
    if force or last is None or now - last >= GUEST_ACTIVITY_WRITE_INTERVAL:
        user.last_login_at = now
        db.commit()


def purge_idle_guests(db: Session, limit: int = 10) -> int:
    """
    Evict guests that look abandoned: no saved files AND not seen for
    GUEST_IDLE_TTL_HOURS. Oldest first. Guests with the IDE open refresh their
    token hourly (see touch_guest), so they are never considered idle.
    Never raises.
    """
    from sqlalchemy import exists

    cutoff = datetime.utcnow() - timedelta(hours=settings.GUEST_IDLE_TTL_HOURS)
    purged = 0
    try:
        idle = (
            db.query(User)
            .filter(
                User.role == UserRole.DEMO,
                User.deleted_at == None,  # noqa: E711
                User.email != LEGACY_SHARED_DEMO_EMAIL,
                User.last_login_at < cutoff,
                # "Abandoned" means the guest owns NO workspace data at all, so
                # evicting it destroys nothing (it's a short TTL for empty accounts).
                ~exists().where(File.user_id == User.id),
                ~exists().where(Folder.user_id == User.id),
                ~exists().where(Project.user_id == User.id),
                ~exists().where(Simulation.user_id == User.id),
                ~exists().where(Conversion.user_id == User.id),
            )
            .order_by(User.last_login_at.asc())
            .limit(limit)
            .all()
        )
        for user in idle:
            purge_guest(db, user)
            purged += 1
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Idle guest purge failed")
        return 0
    return purged


def purge_expired_guests(db: Session, limit: int = 25) -> int:
    """Purge up to `limit` expired guest accounts. Never raises."""
    cutoff = datetime.utcnow() - timedelta(hours=settings.GUEST_ACCOUNT_TTL_HOURS)
    purged = 0
    try:
        expired = (
            db.query(User)
            .filter(
                User.role == UserRole.DEMO,
                User.deleted_at == None,  # noqa: E711
                User.created_at < cutoff,
                User.email != LEGACY_SHARED_DEMO_EMAIL,
            )
            .limit(limit)
            .all()
        )
        for user in expired:
            purge_guest(db, user)
            purged += 1
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Expired guest purge failed")
        return 0
    return purged
