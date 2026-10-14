import os
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
SUBDOMAIN = os.getenv("AMO_SUBDOMAIN")
TOKEN = os.getenv("AMO_TOKEN")

BASE_URL = f"https://{SUBDOMAIN}.amocrm.ru/api/v4"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

r = requests.get(f"{BASE_URL}/account", headers=HEADERS)
print("Status kodi:", r.status_code)

if r.status_code != 200:
    print("Xato! Javob:", r.text)
    raise SystemExit

acc = r.json()
print(f"Ulandi! Akkaunt: {acc['name']} | ID: {acc['id']}")

r = requests.get(f"{BASE_URL}/leads/pipelines", headers=HEADERS)
pipelines = r.json()["_embedded"]["pipelines"]

print("\nVoronkalar va bosqichlar:")
for pipe in pipelines:
    print(f"\n[{pipe['id']}] {pipe['name']}")
    for st in pipe["_embedded"]["statuses"]:
        print(f"    {st['id']:>10}  {st['name']}")
