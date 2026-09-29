"""Generate SQL to reset all LIVE test user passwords to TestPass123!"""
from app.core.security import hash_password

h = hash_password('TestPass123!')
emails = [
    'live.stu.alpha@lgu.edu.pk',
    'live.stu.beta@lgu.edu.pk',
    'live.fac.alpha@lgu.edu.pk',
    'live.fac.beta@lgu.edu.pk',
    'live.stf.student@lgu.edu.pk',
    'live.stf.faculty@lgu.edu.pk',
    'live.mgr.student@lgu.edu.pk',
    'live.mgr.faculty@lgu.edu.pk',
    'live.admin@lgu.edu.pk',
    'live.student@lgu.edu.pk',
]
print(f"-- Password hash: {h}")
for email in emails:
    print(f"UPDATE user_credentials SET password_hash = '{h}' WHERE user_id = (SELECT id FROM users WHERE university_email = '{email}');")
