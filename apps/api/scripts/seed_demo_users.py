"""Create demo users for production testing.

Run from apps/api with production DB env vars set:
    POSTGRES_HOST=... POSTGRES_PORT=... POSTGRES_USER=... \\
    POSTGRES_PASSWORD=... POSTGRES_DB=... \\
    python scripts/seed_demo_users.py

Creates one verified, active user per role. Idempotent: rerunning
updates the existing demo users instead of creating duplicates.
"""

import asyncio
import uuid

from sqlalchemy import select

from app.core.database import async_session_factory
from app.core.security import hash_password
from app.modules.cafeterias.models import Cafeteria
from app.modules.users.models import (
    AccountStatus,
    Role,
    User,
    UserCategory,
    UserCafeteriaRole,
    UserCredential,
)

DEMO_PASSWORD = "UniServe2026!"

DEMO_USERS = [
    {
        "first_name": "Admin",
        "last_name": "User",
        "university_id": "ADMIN001",
        "university_email": "admin@demo.uniserve.pk",
        "category": UserCategory.FACULTY,
        "role": Role.UNIVERSITY_ADMIN,
    },
    {
        "first_name": "Cafeteria",
        "last_name": "Manager",
        "university_id": "MGR001",
        "university_email": "manager@demo.uniserve.pk",
        "category": UserCategory.FACULTY,
        "role": Role.CAFETERIA_MANAGER,
    },
    {
        "first_name": "Cafeteria",
        "last_name": "Staff",
        "university_id": "STAFF001",
        "university_email": "staff@demo.uniserve.pk",
        "category": UserCategory.FACULTY,
        "role": Role.CAFETERIA_STAFF,
    },
    {
        "first_name": "Test",
        "last_name": "Student",
        "university_id": "STD001",
        "university_email": "student@demo.uniserve.pk",
        "category": UserCategory.STUDENT,
        "role": Role.STUDENT,
    },
    {
        "first_name": "Test",
        "last_name": "Faculty",
        "university_id": "FAC001",
        "university_email": "faculty@demo.uniserve.pk",
        "category": UserCategory.FACULTY,
        "role": Role.FACULTY,
    },
]


async def seed() -> None:
    async with async_session_factory() as session:
        cafeteria_result = await session.execute(
            select(Cafeteria).where(Cafeteria.name == "Student Cafeteria")
        )
        cafeteria = cafeteria_result.scalar_one_or_none()

        for user_data in DEMO_USERS:
            result = await session.execute(
                select(User).where(
                    User.university_email == user_data["university_email"]
                )
            )
            user = result.scalar_one_or_none()
            if user is None:
                user = User(
                    id=str(uuid.uuid4()),
                    first_name=user_data["first_name"],
                    last_name=user_data["last_name"],
                    university_id=user_data["university_id"],
                    university_email=user_data["university_email"],
                    category=user_data["category"],
                    role=user_data["role"],
                    status=AccountStatus.ACTIVE,
                    email_verified=True,
                )
                session.add(user)
                await session.flush()
                session.add(
                    UserCredential(
                        user_id=user.id,
                        password_hash=hash_password(DEMO_PASSWORD),
                    )
                )
            else:
                user.role = user_data["role"]
                user.category = user_data["category"]
                user.status = AccountStatus.ACTIVE
                user.email_verified = True
                cred_result = await session.execute(
                    select(UserCredential).where(
                        UserCredential.user_id == user.id
                    )
                )
                cred = cred_result.scalar_one_or_none()
                if cred is None:
                    session.add(
                        UserCredential(
                            user_id=user.id,
                            password_hash=hash_password(DEMO_PASSWORD),
                        )
                    )
                else:
                    cred.password_hash = hash_password(DEMO_PASSWORD)

            # Assign manager/staff to the Student Cafeteria
            if cafeteria and user_data["role"] in (
                Role.CAFETERIA_MANAGER,
                Role.CAFETERIA_STAFF,
            ):
                role_result = await session.execute(
                    select(UserCafeteriaRole).where(
                        UserCafeteriaRole.user_id == user.id,
                        UserCafeteriaRole.cafeteria_id == cafeteria.id,
                    )
                )
                if role_result.scalar_one_or_none() is None:
                    session.add(
                        UserCafeteriaRole(
                            user_id=user.id,
                            cafeteria_id=cafeteria.id,
                            role=user_data["role"],
                        )
                    )

        await session.commit()
        print(f"Created/updated {len(DEMO_USERS)} demo users.")


if __name__ == "__main__":
    asyncio.run(seed())
