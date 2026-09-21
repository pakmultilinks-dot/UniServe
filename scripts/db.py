#!/usr/bin/env python3
"""UniServe — Database Migration Helper Script.

Usage:
    python scripts/db.py migrate    — Run pending migrations
    python scripts/db.py revision   — Create a new migration
    python scripts/db.py current    — Show current migration
    python scripts.db.py history    — Show migration history
    python scripts.db.py reset      — Reset database (development only!)
"""

import subprocess
import sys


def run_command(cmd: list[str], description: str) -> None:
    """Run a shell command and display the result."""
    print(f"\n{'='*60}")
    print(f"  {description}")
    print(f"{'='*60}")
    result = subprocess.run(cmd, cwd="apps/api", capture_output=False)
    if result.returncode != 0:
        print(f"❌ Command failed with exit code {result.returncode}")
        sys.exit(1)
    print(f"✅ {description} completed.")


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    command = sys.argv[1]

    if command == "migrate":
        run_command(["alembic", "upgrade", "head"], "Running database migrations")
    elif command == "revision":
        message = sys.argv[2] if len(sys.argv) > 2 else "auto"
        run_command(
            ["alembic", "revision", "--autogenerate", "-m", message],
            f"Creating migration: {message}",
        )
    elif command == "current":
        run_command(["alembic", "current"], "Current migration")
    elif command == "history":
        run_command(["alembic", "history"], "Migration history")
    elif command == "reset":
        confirm = input("⚠️  Are you sure you want to reset the database? (yes/no): ")
        if confirm.lower() == "yes":
            subprocess.run(["docker", "compose", "down", "-v"])
            subprocess.run(["docker", "compose", "up", "-d", "postgres"])
            run_command(["alembic", "upgrade", "head"], "Database reset and migration")
        else:
            print("Aborted.")
    else:
        print(f"Unknown command: {command}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
