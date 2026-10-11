"""Phase 60 (Workstream G) — rule-based fixture/maintenance hygiene.

Dry-run by default. Replaces the stale Phase-17 ``scripts/cleanup_test_data.py``
scope (which targeted a different database and nonexistent tables) with
explicit, documented rules. Two rule classes:

**Applied only with ``--execute``** (safe, reversible-in-meaning):
- R1: E2E cafeteria deactivation (set ``is_active=False`` — deactivation,
  never deletion).
- R4: stale session reaping (``reap_sessions`` — behaviorally dead rows).
- R5: stale payment reconciliation (``reconcile_stale_payments``).

**Report-only, never applied by this script** (kept conservative):
- R2: item-less cancelled orders (cancelled + zero items + zero payments +
  past order_date — Phase 59 P3-6 residue). Orders are business records;
  deletion is deferred to an explicit, reviewed decision.
- R3: duplicate daily-menu rows (same cafeteria+date, >1 row). Reporting
  only — the published-unique invariant is preserved elsewhere.
- R6: fixture account census (``live.%`` email pattern + non-active users).
  Users are never deleted here (cascades); listed for review.

Usage:
    python -m scripts.fixture_hygiene            # preview (default)
    python -m scripts.fixture_hygiene --execute  # apply R1/R4/R5
"""

import argparse
import asyncio
import json
from datetime import UTC, date, datetime

from sqlalchemy import func, select

from app.core.config import settings
from app.core.database import async_session_factory
from app.modules.auth.service import reap_sessions
from app.modules.cafeterias.models import Cafeteria
from app.modules.menus.models import DailyMenu
from app.modules.orders.models import Order, OrderStatus
from app.modules.payments.models import Payment
from app.modules.payments.service import reconcile_stale_payments
from app.modules.users.models import AccountStatus, User  # noqa: F401 — mapper

# Documented Phase 59 P3-5 E2E residue cafeteria (E2E_PRODUCT_TESTING.md).
E2E_CAFETERIA_ID = "50d67d4b-841b-43c4-b60d-eeb1cf68152a"


def _database_identity() -> dict[str, str]:
    return {
        "host": settings.POSTGRES_HOST,
        "port": str(settings.POSTGRES_PORT),
        "user": settings.POSTGRES_USER,
        "database": settings.POSTGRES_DB,
        "app_env": settings.APP_ENV,
    }


async def _rule_e2e_cafeteria(db, *, execute: bool) -> dict:
    result = await db.execute(
        select(Cafeteria).where(Cafeteria.id == E2E_CAFETERIA_ID)
    )
    cafeteria = result.scalar_one_or_none()
    if cafeteria is None:
        return {"rule": "R1_e2e_cafeteria_deactivation", "found": False}
    report = {
        "rule": "R1_e2e_cafeteria_deactivation",
        "found": True,
        "cafeteria_id": cafeteria.id,
        "name": cafeteria.name,
        "is_active": cafeteria.is_active,
        "applied": False,
    }
    if execute and cafeteria.is_active:
        cafeteria.is_active = False
        report["is_active"] = False
        report["applied"] = True
    return report


async def _rule_itemless_cancelled_orders(db) -> dict:
    from app.modules.orders.models import OrderItem

    result = await db.execute(
        select(Order).where(Order.status == OrderStatus.CANCELLED)
    )
    residue = []
    today = date.today()
    for order in result.scalars().all():
        if order.order_date >= today:
            continue
        item_count = (
            await db.execute(
                select(func.count()).select_from(OrderItem).where(
                    OrderItem.order_id == order.id
                )
            )
        ).scalar_one()
        payment_count = (
            await db.execute(
                select(func.count()).select_from(Payment).where(
                    Payment.order_id == order.id
                )
            )
        ).scalar_one()
        if item_count == 0 and payment_count == 0:
            residue.append(
                {
                    "order_id": order.id,
                    "order_number": order.order_number,
                    "order_date": order.order_date.isoformat(),
                    "total_amount": order.total_amount,
                }
            )
    return {
        "rule": "R2_itemless_cancelled_orders",
        "policy": "report_only — deletion deferred to reviewed decision",
        "count": len(residue),
        "orders": residue,
    }


async def _rule_duplicate_daily_menus(db) -> dict:
    rows = (
        await db.execute(
            select(
                DailyMenu.cafeteria_id,
                DailyMenu.menu_date,
                func.count().label("n"),
            )
            .group_by(DailyMenu.cafeteria_id, DailyMenu.menu_date)
            .having(func.count() > 1)
        )
    ).all()
    return {
        "rule": "R3_duplicate_daily_menu_rows",
        "policy": "report_only",
        "duplicate_groups": [
            {
                "cafeteria_id": r.cafeteria_id,
                "menu_date": r.menu_date.isoformat(),
                "rows": r.n,
            }
            for r in rows
        ],
    }


async def _rule_fixture_users(db) -> dict:
    live_pattern_count = (
        await db.execute(
            select(func.count())
            .select_from(User)
            .where(User.university_email.like("live.%"))
        )
    ).scalar_one()
    non_active = (
        await db.execute(
            select(User.status, func.count())
            .where(User.status != AccountStatus.ACTIVE)
            .group_by(User.status)
        )
    ).all()
    return {
        "rule": "R6_fixture_account_census",
        "policy": "report_only — users never deleted here (FK cascades)",
        "live_prefix_email_count": live_pattern_count,
        "non_active_by_status": {r[0].value: r[1] for r in non_active},
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Apply R1/R4/R5 (R2/R3/R6 are always report-only).",
    )
    args = parser.parse_args()

    mode = "EXECUTE (R1/R4/R5)" if args.execute else "DRY-RUN (no changes)"
    print(f"[fixture_hygiene] mode={mode}")
    print(f"[fixture_hygiene] target database: {_database_identity()}")

    report: dict = {
        "mode": mode,
        "database": _database_identity(),
        "generated_at": datetime.now(UTC).isoformat(),
    }

    async with async_session_factory() as session:
        report["R1"] = await _rule_e2e_cafeteria(session, execute=args.execute)

        reap_preview = await reap_sessions(session, dry_run=True)
        report["R4_stale_sessions_preview"] = reap_preview
        if args.execute:
            reap_applied = await reap_sessions(session, dry_run=False)
            report["R4_stale_sessions_applied"] = reap_applied

        payments_preview = await reconcile_stale_payments(session, dry_run=True)
        report["R5_stale_payments_preview"] = payments_preview
        if args.execute:
            payments_applied = await reconcile_stale_payments(session, dry_run=False)
            report["R5_stale_payments_applied"] = payments_applied

        # Report-only rules — identical in both modes (never mutate here).
        report["R2"] = await _rule_itemless_cancelled_orders(session)
        report["R3"] = await _rule_duplicate_daily_menus(session)
        report["R6"] = await _rule_fixture_users(session)

        if args.execute:
            await session.commit()

    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
