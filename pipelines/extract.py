import os
import json
import time
import requests
from pathlib import Path
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")
BASE_URL = f"https://{os.getenv('AMO_SUBDOMAIN')}.amocrm.ru/api/v4"
HEADERS = {"Authorization": f"Bearer {os.getenv('AMO_TOKEN')}"}

RAW_DIR = Path(os.getenv("AMO_RAW_DIR", str(PROJECT_ROOT / "data" / "raw")))
SESSION = requests.Session()
SESSION.mount("https://", HTTPAdapter(max_retries=Retry(
    total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"], respect_retry_after_header=True,
)))


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
        r = SESSION.get(f"{BASE_URL}/{endpoint}", headers=HEADERS, params=params, timeout=(10, 60))

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
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_DIR / f"{name}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  -> saqlandi: {path}\n")


def main():
    for key in ["AMO_SUBDOMAIN", "AMO_TOKEN"]:
        value = os.getenv(key, "")
        if not value or value.startswith("your_"):
            raise ValueError(f"{key} sozlanmagan. Asosiy .env faylini to'ldiring")

    # Fetch every endpoint before saving; a failed request must fail the Airflow task.
    print("amoCRM API -> JSON...")
    datasets = {
        "leads": get_all("leads", "leads", {"with": "contacts"}),
        "contacts": get_all("contacts", "contacts"),
        "pipelines": get_all("leads/pipelines", "pipelines"),
        "users": get_all("users", "users"),
    }
    for name, records in datasets.items():
        save(name, records)
    print("Tayyor! " + " | ".join(f"{name}: {len(rows)}" for name, rows in datasets.items()))


if __name__ == "__main__":
    main()
