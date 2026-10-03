"""Backfill the cash payment ledger for completed cash orders (P2-2).

Phase 43 (closing Phase 42 P2-2): reporting sums SUCCEEDED payments, but
cash payments used to stay PENDING forever (and scheduled cash orders had
no payment row at all), so revenue showed Rs 0. The live API now confirms
cash payments at handover (collection / READY→COMPLETED), and this script
backfills the historical rows that predate that wiring:

- COMPLETED cash order with a PENDING cash payment → confirm to SUCCEEDED
- COMPLETED cash order with no payment row → create + confirm one for the
  order total (provider_name="cash", idempotency_key="cash_<order_id>")

Never touches non-cash orders, non-completed orders, or payments in any
other state (SUCCEEDED / CANCELLED / REFUNDED are left alone).

Idempotent: safe to re-run.

Usage (inside the API container, which carries the app + DB env):
    docker cp apps/api/scripts/backfill_completed_cash_payments.py uniserve_api:/app/scripts/
    docker exec uniserve_api python scripts/backfill_completed_cash_payments.py
"""

import asyncio

from app.core.database import async_session_factory
from app.modules.payments.service import backfill_completed_cash_payments

# Imported so SQLAlchemy can configure mappers for related models
# (payments.user_id has a foreign key to users.id). Same pattern as the
# existing seed scripts.
from app.modules.users.models import User  # noqa: F401


async def main() -> None:
    async with async_session_factory() as session:
        summary = await backfill_completed_cash_payments(session)
        await session.commit()

    print("Cash payment ledger backfill complete.")
    print(f"  Completed cash orders scanned : {summary['completed_cash_orders']}")
    print(f"  Payments confirmed (PENDING→SUCCEEDED) : {summary['payments_confirmed']}")
    print(f"  Payments created (scheduled cash, none existed) : {summary['payments_created']}")


if __name__ == "__main__":
    asyncio.run(main())
