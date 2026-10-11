import os
import time
import random

import requests
from dotenv import load_dotenv

load_dotenv()
BASE_URL = f"https://{os.getenv('AMO_SUBDOMAIN')}.amocrm.ru/api/v4"
HEADERS = {"Authorization": f"Bearer {os.getenv('AMO_TOKEN')}"}
random.seed(7)


MANAGERS = [
    {"name": "Jahongir Tursunov", "email": "jahongir.tursunov@example.com"},
    {"name": "Sardor Mirzayev",   "email": "sardor.mirzayev@example.com"},
    {"name": "Bobur Islomov",     "email": "bobur.islomov@example.com"},
    {"name": "Zarina Hamidova",   "email": "zarina.hamidova@example.com"},
]
PASSWORD = "TestSavdo2026!"

WEIGHTS = {
    "Won":  [20, 25, 15, 40],   
    "Lost": [30, 20, 35, 15],   
    "Open": [25, 25, 25, 25],
}
WON, LOST = 142, 143


def get_all(endpoint: str, key: str, params: dict | None = None) -> list:
    params = dict(params or {}, limit=250)
    page, result = 1, []
    while True:
        params["page"] = page
        r = requests.get(f"{BASE_URL}/{endpoint}", headers=HEADERS, params=params)
        if r.status_code == 204:
            break
        r.raise_for_status()
        items = r.json()["_embedded"][key]
        result.extend(items)
        if len(items) < 250:
            break
        page += 1
        time.sleep(0.3)
    return result


def create_managers() -> list[int]:
    existing = {u["email"]: u["id"] for u in get_all("users", "users")}
    to_create = [m for m in MANAGERS if m["email"] not in existing]

    if to_create:
        payload = [{"name": m["name"], "email": m["email"], "password": PASSWORD} for m in to_create]
        r = requests.post(f"{BASE_URL}/users", headers=HEADERS, json=payload)
        if r.status_code not in (200, 201):
            print(f"Menejer yaratishda xato ({r.status_code}):\n{r.text}")
            raise SystemExit(1)
        for u in r.json()["_embedded"]["users"]:
            existing[u["email"]] = u["id"]
            print(f"  + yaratildi: {u['name']}")
    else:
        print("  Menejerlar allaqachon bor — qayta yaratilmadi")

    return [existing[m["email"]] for m in MANAGERS]


def outcome(status_id: int) -> str:
    return "Won" if status_id == WON else "Lost" if status_id == LOST else "Open"


def patch_in_batches(endpoint: str, items: list) -> None:
    for i in range(0, len(items), 250):          # bir so'rovda ko'pi bilan 250 ta
        r = requests.patch(f"{BASE_URL}/{endpoint}", headers=HEADERS, json=items[i:i + 250])
        r.raise_for_status()
        time.sleep(0.5)


def main():
    print("1) Menejerlar...")
    manager_ids = create_managers()

    print("\n2) Bitimlarni taqsimlash...")
    leads = get_all("leads", "leads", {"with": "contacts"})

    lead_updates, contact_updates = [], {}
    counts = {m["name"]: 0 for m in MANAGERS}

    for lead in leads:
        idx = random.choices(range(len(MANAGERS)), weights=WEIGHTS[outcome(lead["status_id"])])[0]
        uid = manager_ids[idx]
        counts[MANAGERS[idx]["name"]] += 1
        lead_updates.append({"id": lead["id"], "responsible_user_id": uid})
        # mijoz ham o'sha menejerga biriktiriladi
        for c in lead.get("_embedded", {}).get("contacts", []):
            contact_updates[c["id"]] = {"id": c["id"], "responsible_user_id": uid}

    patch_in_batches("leads", lead_updates)
    patch_in_batches("contacts", list(contact_updates.values()))

    for name, n in counts.items():
        print(f"  {name:<18} {n:>4} ta bitim")
    print(f"\nTayyor! ✅ {len(lead_updates)} ta bitim va {len(contact_updates)} ta kontakt taqsimlandi.")
    print("Endi:  python extract.py  ->  python transform_load.py")


if __name__ == "__main__":
    main()
