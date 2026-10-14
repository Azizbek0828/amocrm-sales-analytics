import os
import json
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import URL, create_engine, text
 
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")
RAW_DIR = Path(os.getenv("AMO_RAW_DIR", str(PROJECT_ROOT / "data" / "raw")))
TIMEZONE = "Asia/Tashkent"
 
WON_STATUS, LOST_STATUS = 142, 143
 
 
# ============================== EXTRACT (fayldan o'qish) ==============================
def read_raw(name: str) -> list:
    with open(os.path.join(RAW_DIR, f"{name}.json"), encoding="utf-8") as f:
        return json.load(f)
 
 
def to_datetime(series: pd.Series) -> pd.Series:
    """Unix vaqt (soniyalar) -> Toshkent vaqti (timezone'siz, SQL uchun qulay)."""
    return (pd.to_datetime(series, unit="s", utc=True)
              .dt.tz_convert(TIMEZONE)
              .dt.tz_localize(None))
 
 
# ============================== TRANSFORM ==============================
def transform_stages(pipelines: list) -> pd.DataFrame:
    rows = []
    for p in pipelines:
        for s in p["_embedded"]["statuses"]:
            rows.append({
                "pipeline_id": p["id"],
                "pipeline_name": p["name"],
                "status_id": s["id"],
                "stage_name": s["name"],
                "stage_order": s["sort"],          
            })
    df = pd.DataFrame(rows, columns=["pipeline_id", "pipeline_name", "status_id", "stage_name", "stage_order"]).sort_values(["pipeline_id", "stage_order"])
    df["stage_order"] = df.groupby("pipeline_id").cumcount() + 1   
    return df
 
 
def transform_users(users: list, leads: pd.DataFrame) -> pd.DataFrame:
    active_ids = set(leads["responsible_user_id"].dropna())
    return pd.DataFrame([{
        "user_id": u["id"],
        "user_name": u["name"],
    } for u in users if u["id"] in active_ids], columns=["user_id", "user_name"])
 
 
def get_phone(custom_fields) -> str | None:
    """Kontaktning custom_fields_values ichidan telefon raqamini topadi."""
    for field in custom_fields or []:
        if field.get("field_code") == "PHONE" and field.get("values"):
            return field["values"][0]["value"]
    return None
 
 
def transform_contacts(contacts: list) -> pd.DataFrame:
    df = pd.DataFrame([{
        "contact_id": c["id"],
        "full_name": c.get("name"),
        "first_name": c.get("first_name"),
        "last_name": c.get("last_name"),
        "phone": get_phone(c.get("custom_fields_values")),
        "created_at": c.get("created_at"),
    } for c in contacts], columns=["contact_id", "full_name", "first_name", "last_name", "phone", "created_at"])
    df["created_at"] = to_datetime(df["created_at"])
    return df
 
 
def transform_leads(leads: list) -> pd.DataFrame:
    rows = []
    for l in leads:
        emb = l.get("_embedded", {})
        tags = [t["name"] for t in emb.get("tags", [])]
        contacts = emb.get("contacts", [])
        main_contact = next((c["id"] for c in contacts if c.get("is_main")),
                            contacts[0]["id"] if contacts else None)
        rows.append({
            "lead_id": l["id"],
            "lead_name": l["name"],
            "price": l.get("price") or 0,
            "pipeline_id": l["pipeline_id"],
            "status_id": l["status_id"],
            "responsible_user_id": l.get("responsible_user_id"),
            "contact_id": main_contact,
            "source": tags[0] if tags else "Неизвестно",   
            "created_at": l.get("created_at"),
            "updated_at": l.get("updated_at"),
            "closed_at": l.get("closed_at"),
        })
 
    df = pd.DataFrame(rows, columns=["lead_id", "lead_name", "price", "pipeline_id", "status_id", "responsible_user_id", "contact_id", "source", "created_at", "updated_at", "closed_at"])
 

    for col in ["created_at", "updated_at", "closed_at"]:
        df[col] = to_datetime(df[col])
 

    df["product"] = df["lead_name"].astype("string").str.split(" — ").str[0]
 

    df["outcome"] = "Open"
    df.loc[df["status_id"] == WON_STATUS, "outcome"] = "Won"
    df.loc[df["status_id"] == LOST_STATUS, "outcome"] = "Lost"
 

    df["days_to_close"] = (df["closed_at"] - df["created_at"]).dt.days
 
    df["contact_id"] = df["contact_id"].astype("Int64")
    df["days_to_close"] = df["days_to_close"].astype("Int64")
    return df
 
 
# ============================== LOAD ==============================
def get_engine():
    for name in ["PG_USER", "PG_PASSWORD", "PG_DB"]:
        if not os.getenv(name):
            raise ValueError(f"{name} sozlanmagan")
    # URL.create handles special characters in database passwords correctly.
    url = URL.create(
        "postgresql+psycopg2", username=os.getenv("PG_USER"),
        password=os.getenv("PG_PASSWORD"), host=os.getenv("PG_HOST", "localhost"),
        port=int(os.getenv("PG_PORT", "5432")), database=os.getenv("PG_DB"),
    )
    return create_engine(url, connect_args={"connect_timeout": 10})


def load(engine, tables: dict) -> None:
    # PostgreSQL commits the complete refresh together, or rolls all changes back.
    with engine.begin() as conn:
        for name, df in tables.items():
            df.to_sql(name, conn, if_exists="replace", index=False)
            print(f"  {name:<14} -> {len(df):>4} qator yuklandi")
        conn.execute(text("ALTER TABLE dim_users ADD PRIMARY KEY (user_id)"))
        conn.execute(text("ALTER TABLE dim_contacts ADD PRIMARY KEY (contact_id)"))
        conn.execute(text("ALTER TABLE fact_leads ADD PRIMARY KEY (lead_id)"))
        conn.execute(text("ALTER TABLE dim_stages ADD PRIMARY KEY (pipeline_id, status_id)"))


def main():
    print("Transform...")
    fact_leads = transform_leads(read_raw("leads"))
    tables = {
        "dim_stages": transform_stages(read_raw("pipelines")),
        "dim_users": transform_users(read_raw("users"), fact_leads),
        "dim_contacts": transform_contacts(read_raw("contacts")),
        "fact_leads": fact_leads,
    }
 
    leads = tables["fact_leads"]
    print(f"  Bitimlar: {len(leads)} | Won: {(leads.outcome == 'Won').sum()} | "
          f"Lost: {(leads.outcome == 'Lost').sum()} | Open: {(leads.outcome == 'Open').sum()}")
 
    print("\nLoad -> PostgreSQL...")
    load(get_engine(), tables)
    print("\nTayyor! ✅")
 
 
if __name__ == "__main__":
    main()
 