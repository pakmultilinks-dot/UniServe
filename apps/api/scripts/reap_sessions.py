"""Phase 60 (Workstream D) — session reaping maintenance script.

Dry-run by default; nothing is deleted unless ``--execute`` is passed.
Prints the target database identity first (Phase 60 rule: always record
host/port/name/user before any mutation) and never touches tokens,
semantics, or non-eligible rows.

Usage:
    python -m scripts.reap_sessions                 # preview (dry-run)
    python -m scripts.reap_sessions --execute       # apply
    python -m scripts.reap_sessions --execute --revoked-grace-days 7 \
        --inactive-grace-days 1 --protect-session-id <session-id>
"""

import argparse
import asyncio
import json

from app.core.config import settings
from app.core.database import async_session_factory
from app.modules.auth.service import reap_sessions
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
        help="Actually delete eligible session rows (default: dry-run).",
    )
    parser.add_argument("--revoked-grace-days", type=int, default=7)
    parser.add_argument("--inactive-grace-days", type=int, default=1)
    parser.add_argument(
        "--protect-session-id",
        default=None,
        help="Never delete this session id (e.g. the operator's session).",
    )
    args = parser.parse_args()

    mode = "EXECUTE" if args.execute else "DRY-RUN (no changes)"
    print(f"[reap_sessions] mode={mode}")
    print(f"[reap_sessions] target database: {_database_identity()}")

    async with async_session_factory() as session:
        summary = await reap_sessions(
            session,
            revoked_grace_days=args.revoked_grace_days,
            inactive_grace_days=args.inactive_grace_days,
            protect_session_id=args.protect_session_id,
            dry_run=not args.execute,
        )
        if args.execute:
            await session.commit()

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
