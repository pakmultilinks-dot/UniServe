"""Phase 60 (Workstream E) — stale payment reconciliation script.

Dry-run by default; nothing is mutated unless ``--execute`` is passed.
Classification follows established business rules only:

- payment PENDING/PROCESSING on a CANCELLED order → CANCELLED
  (order cancelled before payment completed);
- PENDING cash payment on a COMPLETED cash order → SUCCEEDED
  (sanctioned Phase-43 ledger rule; money already received at handover).

Sandbox PENDING/PROCESSING payments on non-terminal orders are
deliberately left alone (the user may be mid-payment).

Usage:
    python -m scripts.reconcile_payments                 # preview
    python -m scripts.reconcile_payments --execute       # apply
    python -m scripts.reconcile_payments --execute --stale-after-hours 24
"""

import argparse
import asyncio
import json

from app.core.config import settings
from app.core.database import async_session_factory
from app.modules.payments.service import (
    Payment,  # noqa: F401 — mapper configuration
    PaymentAttempt,  # noqa: F401
    WebhookEvent,  # noqa: F401
    reconcile_stale_payments,
)
from app.modules.users.models import User  # noqa: F401 — mapper configuration


def _database_identity() -> dict[str, str]:
    return {
        "host": settings.POSTGRES_HOST,
        "port": str(settings.POSTGRES_PORT),
        "user": settings.POSTGRES_USER,
        "database": settings.POSTGRES_DB,
        "app_env": settings.APP_ENV,
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually transition eligible payments (default: dry-run).",
    )
    parser.add_argument("--stale-after-hours", type=int, default=24)
    args = parser.parse_args()

    mode = "EXECUTE" if args.execute else "DRY-RUN (no changes)"
    print(f"[reconcile_payments] mode={mode}")
    print(f"[reconcile_payments] target database: {_database_identity()}")

    async with async_session_factory() as session:
        summary = await reconcile_stale_payments(
            session,
            stale_after_hours=args.stale_after_hours,
            dry_run=not args.execute,
        )
        if args.execute:
            await session.commit()

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
