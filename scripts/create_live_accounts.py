#!/usr/bin/env python3
"""Create live verification accounts in the database."""
import uuid
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + "/../apps/api")

from app.core.security import hash_password

pwd_hash = hash_password("TestPass123!")

users = [
    ("live.stu.alpha@lgu.edu.pk", "Alpha", "Student", "LIVE-STU-ALPHA", "student", "student"),
    ("live.stu.beta@lgu.edu.pk", "Beta", "Student", "LIVE-STU-BETA", "student", "student"),
    ("live.fac.alpha@lgu.edu.pk", "Alpha", "Faculty", "LIVE-FAC-ALPHA", "faculty", "faculty"),
    ("live.fac.beta@lgu.edu.pk", "Beta", "Faculty", "LIVE-FAC-BETA", "faculty", "faculty"),
    ("live.stf.student@lgu.edu.pk", "Student", "Staff", "LIVE-STF-STU", "student", "cafeteria_staff"),
    ("live.stf.faculty@lgu.edu.pk", "Faculty", "Staff", "LIVE-STF-FAC", "faculty", "cafeteria_staff"),
    ("live.mgr.student@lgu.edu.pk", "Student", "Manager", "LIVE-MGR-STU", "student", "cafeteria_manager"),
    ("live.mgr.faculty@lgu.edu.pk", "Faculty", "Manager", "LIVE-MGR-FAC", "faculty", "cafeteria_manager"),
    ("live.admin@lgu.edu.pk", "Admin", "User", "LIVE-ADM", "faculty", "university_admin"),
]

lines = []
for email, first, last, uid, cat, role in users:
    user_id = str(uuid.uuid4())
    cred_id = str(uuid.uuid4())
    lines.append(
        f"INSERT INTO users (id, first_name, last_name, university_id, university_email, category, role, status, email_verified, created_at, updated_at) "
        f"VALUES ('{user_id}', '{first}', '{last}', '{uid}', '{email}', '{cat}', '{role}', 'active', true, now(), now()) "
        f"ON CONFLICT (university_id) DO NOTHING;"
    )
    lines.append(
        f"INSERT INTO user_credentials (id, user_id, password_hash, created_at, updated_at) "
        f"VALUES ('{cred_id}', '{user_id}', '{pwd_hash}', now(), now()) "
        f"ON CONFLICT (user_id) DO NOTHING;"
    )

print("\n".join(lines))
