"""No-show tracking and suspension policy.

When an order goes uncollected past its pickup deadline, a no-show is recorded.
After exceeding the threshold for the user's category, ordering is suspended.
"""

from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.modules.orders.models import NoShow

logger = structlog.get_logger(__name__)


async def record_no_show(
    *,
    db: AsyncSession,
    user_id: str,
    order_id: str,
    cafeteria_id: str,
) -> None:
    """Record a no-show event and check suspension policy."""
    from app.modules.users.models import User, UserCategory

    # Create no-show record
    noshow = NoShow(
        user_id=user_id,
        order_id=order_id,
        cafeteria_id=cafeteria_id,
    )
    db.add(noshow)

    # Increment user's no-show count
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if user is None:
        logger.warning("noshow_user_not_found", user_id=user_id)
        return

    user.no_show_count += 1

    # Check suspension policy based on category
    threshold = settings.NOSHOW_STUDENT_THRESHOLD
    window_days = settings.NOSHOW_STUDENT_WINDOW_DAYS
    suspension_days = settings.NOSHOW_STUDENT_SUSPENSION_DAYS

    if user.category == UserCategory.FACULTY:
        threshold = settings.NOSHOW_FACULTY_THRESHOLD
        window_days = settings.NOSHOW_FACULTY_WINDOW_DAYS
        suspension_days = settings.NOSHOW_FACULTY_SUSPENSION_DAYS

    # Count no-shows in the window
    cutoff = datetime.now(UTC) - timedelta(days=window_days)
    count_result = await db.execute(
        select(func.count(NoShow.id)).where(
            NoShow.user_id == user_id,
            NoShow.created_at >= cutoff,
        )
    )
    noshow_count = count_result.scalar() or 0

    if noshow_count >= threshold and not user.ordering_suspended:
        user.ordering_suspended = True
        user.ordering_suspended_until = datetime.now(UTC) + timedelta(days=suspension_days)
        user.ordering_suspension_reason = (
            f"Auto-suspended: {noshow_count} no-shows in {window_days} days "
            f"(threshold: {threshold})"
        )
        logger.info(
            "user_suspended_no_show",
            user_id=user_id,
            noshow_count=noshow_count,
            suspension_until=user.ordering_suspended_until.isoformat(),
        )

    await db.flush()


async def check_suspension(*, db: AsyncSession, user_id: str) -> bool:
    """Check if a user's ordering suspension has expired.

    Returns True if the user is currently suspended.
    """
    from app.modules.users.models import User

    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if user is None:
        return False

    if not user.ordering_suspended:
        return False

    # Check if suspension has expired
    if user.ordering_suspended_until and datetime.now(UTC) > user.ordering_suspended_until:
        user.ordering_suspended = False
        user.ordering_suspended_until = None
        user.ordering_suspension_reason = None
        await db.flush()
        return False

    return True


async def get_no_show_count(
    *,
    db: AsyncSession,
    user_id: str,
    days: int = 30,
) -> int:
    """Get the number of no-shows for a user within a time window."""
    cutoff = datetime.now(UTC) - timedelta(days=days)
    result = await db.execute(
        select(func.count(NoShow.id)).where(
            NoShow.user_id == user_id,
            NoShow.created_at >= cutoff,
        )
    )
    return result.scalar() or 0
