import os
import json
import time

import requests
from dotenv import load_dotenv

load_dotenv()
BASE_URL = f"https://{os.getenv('AMO_SUBDOMAIN')}.amocrm.ru/api/v4"
HEADERS = {"Authorization": f"Bearer {os.getenv('AMO_TOKEN')}"}

RAW_DIR = os.path.join("data", "raw")
os.makedirs(RAW_DIR, exist_ok=True)


def get_all(endpoint: str, key: str, params: dict | None = None) -> list:
    """
    API ma'lumotni sahifalab (pagination) beradi: bir so'rovda ko'pi bilan 250 ta.
    Shuning uchun sahifama-sahifa so'raymiz, ma'lumot tugaguncha.
    """
    params = dict(params or {})
    params["limit"] = 250
    page = 1
    result = []

    while True:
        params["page"] = page
        r = requests.get(f"{BASE_URL}/{endpoint}", headers=HEADERS, params=params)

        if r.status_code == 204:      
            break
        r.raise_for_status()           

        items = r.json()["_embedded"][key]
        result.extend(items)
        print(f"  {endpoint}: {page}-sahifa, +{len(items)} ta (jami {len(result)})")

        if len(items) < 250:           
            break
        page += 1
        time.sleep(0.3)               

    return result


def save(name: str, data) -> None:
    path = os.path.join(RAW_DIR, f"{name}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  -> saqlandi: {path}\n")


def main():
    print("Bitimlar...")
   
    leads = get_all("leads", "leads", {"with": "contacts"})
    save("leads", leads)

    print("Kontaktlar...")
    contacts = get_all("contacts", "contacts")
    save("contacts", contacts)

    print("Voronkalar...")
    r = requests.get(f"{BASE_URL}/leads/pipelines", headers=HEADERS)
    r.raise_for_status()
    save("pipelines", r.json()["_embedded"]["pipelines"])

    print("Foydalanuvchilar...")
    users = get_all("users", "users")
    save("users", users)

    print("=" * 40)
    print(f"Tayyor! Bitimlar: {len(leads)} | Kontaktlar: {len(contacts)} | Foydalanuvchilar: {len(users)}")


if __name__ == "__main__":
    main()
