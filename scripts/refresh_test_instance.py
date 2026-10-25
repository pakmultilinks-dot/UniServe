"""Explicit demo maintenance. Default is a read-only plan, never startup seeding.

Use --credentials with the operator's private four-test-accounts.json file.
--apply requires the exact deployed API commit and disabled startup seeding.
Backups/credentials must stay outside the Git checkout. No payment endpoint
is used; account cleanup is soft deletion with session revocation.
"""

import argparse
from datetime import datetime
import hashlib
import io
import json
from pathlib import Path
import re
import urllib.error
import urllib.request
from zoneinfo import ZoneInfo

BASE = "https://uniserve-api.onrender.com"
REPO = Path(__file__).resolve().parent.parent
ROLES = {
    "student": "student",
    "faculty": "faculty",
    "admin": "university_admin",
    "staff": "cafeteria_staff",
}


def api(method, path, token=None, body=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(
        BASE + "/api/v1" + path,
        method=method,
        headers=headers,
        data=json.dumps(body).encode() if body is not None else None,
    )
    with urllib.request.urlopen(request, timeout=125) as response:
        raw = response.read()
        return json.loads(raw) if raw else None


def login(account):
    result = api(
        "POST",
        "/auth/login",
        body={"university_email": account["email"], "password": account["password"]},
    )
    return result["user"], result["tokens"]["access_token"]


def users(token):
    found = []
    for offset in range(0, 10000, 200):
        page = api("GET", f"/users/?limit=200&offset={offset}", token)
        found.extend(page["users"])
        if len(found) >= page["total"]:
            return found
    raise RuntimeError("Unexpected user count; refusing an incomplete account plan")


def verify_images(manifest):
    from PIL import Image

    images = sorted(
        {
            item["image_url"]
            for items in manifest["cafeterias"].values()
            for item in items
        }
    )
    for image in images:
        url = BASE + image if image.startswith("/") else image
        if not (
            url.startswith(BASE + "/api/v1/static/food/")
            or url.startswith("https://images.unsplash.com/")
        ):
            raise RuntimeError("Unexpected image host")
        with urllib.request.urlopen(url, timeout=60) as response:
            data = response.read()
            assert response.status == 200
        with Image.open(io.BytesIO(data)) as decoded:
            decoded.verify()
    return len(images)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--credentials", type=Path, required=True)
    parser.add_argument("--backup-dir", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-api-commit")
    parser.add_argument("--retire-legacy-accounts", action="store_true")
    args = parser.parse_args()
    backup = args.backup_dir.resolve()
    if backup.is_relative_to(REPO) or args.credentials.resolve().is_relative_to(REPO):
        raise RuntimeError(
            "Keep private credentials and maintenance backups outside Git"
        )
    backup.mkdir(parents=True, exist_ok=True, mode=0o700)
    accounts = json.loads(args.credentials.read_text(encoding="utf-8"))
    assert set(accounts) == set(ROLES), "Exactly four configured test accounts required"
    tokens, identities = {}, {}
    for name, role in ROLES.items():
        user, tokens[name] = login(accounts[name])
        assert user["role"] == role and user["email_verified"]
        identities[name] = user["id"]
    assert len(set(identities.values())) == 4
    health = api("GET", "/health")
    manifest_path = REPO / "scripts/fresh_test_menu.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    image_count = verify_images(manifest)
    admin = tokens["admin"]
    before_users = users(admin)
    legacy = [
        user
        for user in before_users
        if user["university_email"].endswith("@demo.uniserve.pk")
        and user["id"] not in identities.values()
    ]
    cafeterias = api("GET", "/cafeterias/", admin)["cafeterias"]
    state = {"users": before_users, "cafeterias": cafeterias, "catalogues": {}}
    plans = []
    for name, items in manifest["cafeterias"].items():
        matches = [cafe for cafe in cafeterias if cafe["name"] == name]
        assert len(matches) == 1, "Cafeteria must resolve uniquely: " + name
        cafe = matches[0]
        cid = cafe["id"]
        catalog = api("GET", f"/cafeterias/{cid}/menu-items/", admin)
        menus = api("GET", f"/cafeterias/{cid}/daily-menus/", admin)
        inventory = api("GET", f"/cafeterias/{cid}/inventory/", admin)
        state["catalogues"][cid] = {
            "menu": catalog,
            "daily_menus": menus,
            "inventory": inventory,
        }
        assert len({item["name"] for item in items}) == len(items)
        plans.append(
            {
                "cafeteria": name,
                "id": cid,
                "items": len(items),
                "opening_test_stock_per_item": 60,
                "retire_extra_items": sum(
                    item["name"] not in {entry["name"] for entry in items}
                    for item in catalog["items"]
                ),
            }
        )
    receipt = {
        "mode": "apply" if args.apply else "plan",
        "images_decoded": image_count,
        "menu": plans,
        "legacy_demo_accounts": len(legacy),
        "other_domain_accounts_preserved": sum(
            not user["university_email"].endswith("@demo.uniserve.pk")
            for user in before_users
        ),
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
    }
    (backup / "refresh-plan.json").write_text(
        json.dumps(receipt, indent=2), encoding="utf-8"
    )
    print(json.dumps(receipt, indent=2), flush=True)
    if not args.apply:
        return
    assert re.fullmatch(r"[0-9a-f]{40}", args.expected_api_commit or "")
    assert health.get("build_commit") == args.expected_api_commit, (
        "Wrong deployed API revision"
    )
    assert health.get("demo_seed_on_startup") == "disabled", (
        "Stop automatic reseeding first"
    )
    backup_file = backup / (
        "before-refresh-" + datetime.now().strftime("%Y%m%d-%H%M%S") + ".json"
    )
    backup_file.write_text(json.dumps(state, indent=2), encoding="utf-8")

    # Validate all existing drafts before changing either cafeteria.
    for plan in plans:
        cafe = next(cafe for cafe in cafeterias if cafe["id"] == plan["id"])
        today = (
            datetime.now(ZoneInfo(cafe.get("timezone") or "Asia/Karachi"))
            .date()
            .isoformat()
        )
        assert not any(
            menu["menu_date"] == today and menu["status"] == "draft"
            for menu in state["catalogues"][plan["id"]]["daily_menus"]["menus"]
        ), "An existing draft needs operator review before replacement"
    for plan in plans:
        cid = plan["id"]
        entries = manifest["cafeterias"][plan["cafeteria"]]
        previous = state["catalogues"][cid]
        by_name = {item["name"]: item for item in previous["menu"]["items"]}
        selected = []
        for entry in entries:
            if entry["name"] in by_name:
                item = by_name[entry["name"]]
                update = {
                    key: value
                    for key, value in entry.items()
                    if key != "initial_quantity"
                }
                update.update(is_active=True, is_available=True)
                item = api(
                    "PUT", f"/cafeterias/{cid}/menu-items/{item['id']}", admin, update
                )
                api(
                    "POST",
                    f"/cafeterias/{cid}/inventory/",
                    admin,
                    {
                        "menu_item_id": item["id"],
                        "quantity": entry["initial_quantity"],
                        "unit": "portions",
                        "low_threshold": 10,
                    },
                )
            else:
                item = api("POST", f"/cafeterias/{cid}/menu-items/", admin, entry)
            selected.append(item["id"])
        cafe = next(cafe for cafe in cafeterias if cafe["id"] == cid)
        today = (
            datetime.now(ZoneInfo(cafe.get("timezone") or "Asia/Karachi"))
            .date()
            .isoformat()
        )
        for menu in previous["daily_menus"]["menus"]:
            if menu["menu_date"] == today and menu["status"] == "published":
                api(
                    "PATCH",
                    f"/cafeterias/{cid}/daily-menus/{menu['id']}/unpublish",
                    admin,
                )
        drafts = [
            menu
            for menu in previous["daily_menus"]["menus"]
            if menu["menu_date"] == today and menu["status"] == "draft"
        ]
        # Refuse to silently reuse someone else's unfinished draft.
        assert not drafts, "An existing draft needs operator review before replacement"
        menu = api(
            "POST", f"/cafeterias/{cid}/daily-menus/", admin, {"menu_date": today}
        )
        for index, item_id in enumerate(selected):
            api(
                "POST",
                f"/cafeterias/{cid}/daily-menus/{menu['id']}/items",
                admin,
                {
                    "menu_item_id": item_id,
                    "display_order": index,
                    "is_available_today": True,
                },
            )
        api("PATCH", f"/cafeterias/{cid}/daily-menus/{menu['id']}/publish", admin)
        for item in previous["menu"]["items"]:
            if item["id"] not in selected:
                api("DELETE", f"/cafeterias/{cid}/menu-items/{item['id']}", admin)
        published = api("GET", f"/cafeterias/{cid}/daily-menus/today", admin)
        assert published and published["status"] == "published"
        assert {entry["menu_item_id"] for entry in published["items"]} == set(selected)
        print(
            "Published fresh test menu:", plan["cafeteria"], len(selected), flush=True
        )

    if args.retire_legacy_accounts:
        for old in legacy:
            recovered = api(
                "POST",
                f"/users/{old['id']}/recover",
                admin,
                {
                    "university_id": old["university_id"],
                    "reason": "Owner-authorized removal of legacy demo/QA account",
                },
            )
            temporary = recovered["temporary_password"]
            identity, token = login(
                {"email": old["university_email"], "password": temporary}
            )
            assert (
                identity["id"] == old["id"]
                and identity["id"] not in identities.values()
            )
            own_orders = api("GET", "/orders/?days=90", token)["orders"]
            assert all(
                order["status"] in ("completed", "cancelled") for order in own_orders
            ), "Resolve active orders before deleting a legacy account"
            api(
                "DELETE",
                "/users/me",
                token,
                {
                    "password": temporary,
                    "reason": "Replaced by the four requested dummy accounts",
                },
            )
        remaining = users(admin)
        demos = [
            user
            for user in remaining
            if user["university_email"].endswith("@demo.uniserve.pk")
        ]
        assert {user["id"] for user in demos} == set(identities.values())
        assert all(user["status"] == "active" for user in demos)
    receipt["completed"] = True
    (backup / "refresh-completed.json").write_text(
        json.dumps(receipt, indent=2), encoding="utf-8"
    )
    print(
        "Explicit test-instance refresh verified; no payments or database reset",
        flush=True,
    )


if __name__ == "__main__":
    main()
