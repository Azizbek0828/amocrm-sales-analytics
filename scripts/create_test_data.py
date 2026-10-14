import os
import time
import random
from datetime import datetime, timedelta

import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")
BASE_URL = f"https://{os.getenv('AMO_SUBDOMAIN')}.amocrm.ru/api/v4"
HEADERS = {"Authorization": f"Bearer {os.getenv('AMO_TOKEN')}"}

random.seed(42)  

DEALS_COUNT = 500   
DAYS_BACK = 180     

# ---------- Sizning voronkangiz (amo_test.py natijasidan) ----------
PIPELINE_ID = 11388754

# (status_id, ehtimollik og'irligi) — real voronkaga o'xshash taqsimot
STATUSES = [
    (89230658, 10),  # Новая заявка
    (89230662, 10),  # Потребность выявлена
    (89230666, 10),  # Коммерческое предложение отправлено
    (89230670, 8),   # Счёт выставлен
    (89230674, 7),   # Оплата получена
    (142, 25),       # Успешно реализовано
    (143, 30),       # Закрыто и не реализовано
]
CLOSED_STATUSES = {142, 143}

# ---------- Test ma'lumot uchun ro'yxatlar ----------
PRODUCTS = {  
    "Ноутбуки": (5_000_000, 40_000_000),
    "Смартфоны": (2_000_000, 25_000_000),
    "Мониторы": (1_500_000, 12_000_000),
    "Принтеры": (1_000_000, 8_000_000),
    "Комплектующие": (500_000, 6_000_000),
    "Сетевое оборудование": (1_000_000, 15_000_000),
}
SOURCES = ["Telegram", "Instagram", "Звонок", "Сайт", "Рекомендация"]
SOURCE_WEIGHTS = [35, 25, 20, 12, 8]

FIRST_NAMES = ["Aziz", "Jasur", "Dilshod", "Sardor", "Bekzod", "Otabek", "Sherzod",
               "Madina", "Nilufar", "Dilnoza", "Gulnora", "Kamola", "Shahlo", "Malika"]
LAST_NAMES = ["Karimov", "Rahimov", "Tursunov", "Yusupov", "Aliyev", "Saidov",
              "Ergashev", "Nazarov", "Xolmatov", "Qodirov"]


def to_unix(dt: datetime) -> int:
    return int(dt.timestamp())


def make_deal() -> dict:
    now = datetime.now()
    product = random.choice(list(PRODUCTS))
    low, high = PRODUCTS[product]
    price = round(random.randint(low, high), -4)  # 10 000 ga yaxlitlash

    status_id = random.choices([s for s, _ in STATUSES], weights=[w for _, w in STATUSES])[0]
    source = random.choices(SOURCES, weights=SOURCE_WEIGHTS)[0]

    created = now - timedelta(days=random.randint(1, DAYS_BACK), hours=random.randint(0, 10))

    first = random.choice(FIRST_NAMES)
    last = random.choice(LAST_NAMES)
    if first.endswith("a"):          # ayollar uchun familiya: Karimova
        last += "a"
    phone = "+99890" + "".join(random.choices("0123456789", k=7))

    deal = {
        "name": f"{product} — {first} {last}",
        "price": price,
        "pipeline_id": PIPELINE_ID,
        "status_id": status_id,
        "created_at": to_unix(created),
        "_embedded": {
            "tags": [{"name": source}],
            "contacts": [{
                "first_name": first,
                "last_name": last,
                "custom_fields_values": [{
                    "field_code": "PHONE",
                    "values": [{"value": phone, "enum_code": "WORK"}],
                }],
            }],
        },
    }

    # Yopilgan bitimlar uchun yopilish sanasi (yaratilgandan 1–21 kun keyin)
    if status_id in CLOSED_STATUSES:
        closed = min(created + timedelta(days=random.randint(1, 21)), now)
        deal["closed_at"] = to_unix(closed)

    return deal


def main():
    deals = [make_deal() for _ in range(DEALS_COUNT)]

    # API bir so'rovda ko'pi bilan 50 ta bitim qabul qiladi -> 2 qismga bo'lamiz
    created_total = 0
    for i in range(0, len(deals), 50):
        batch = deals[i:i + 50]
        r = requests.post(f"{BASE_URL}/leads/complex", headers=HEADERS, json=batch)
        if r.status_code == 200:
            created_total += len(r.json())
            print(f"{i + 1}-{i + len(batch)} bitimlar yaratildi ✅")
        else:
            print(f"Xato ({r.status_code}):", r.text)
            break
        time.sleep(1)  # API'ni ortiqcha yuklamaslik uchun

    print(f"\nJami yaratildi: {created_total} ta bitim")


if __name__ == "__main__":
    main()
