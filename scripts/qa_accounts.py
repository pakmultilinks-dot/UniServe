"""The four owner-requested dummy accounts; credentials come from Actions secrets."""
import json
import os


def load_qa_accounts():
    raw = os.environ.get("QA_TEST_ACCOUNTS_JSON")
    if not raw:
        raise RuntimeError("QA_TEST_ACCOUNTS_JSON must contain the four test accounts")
    accounts = json.loads(raw)
    if set(accounts) != {"student", "faculty", "admin", "staff"}:
        raise RuntimeError("Exactly student, faculty, admin and staff accounts are required")
    if len({account["email"] for account in accounts.values()}) != 4:
        raise RuntimeError("The four accounts must have distinct identities")
    for account in accounts.values():
        if not account["email"].endswith("@demo.uniserve.pk") or not account["password"]:
            raise RuntimeError("Only configured UniServe dummy accounts may be used")
        if os.environ.get("GITHUB_ACTIONS") == "true":
            print("::add-mask::" + account["password"], flush=True)
    return accounts
