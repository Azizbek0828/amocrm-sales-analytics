import os
import json
 
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
 
load_dotenv()
RAW_DIR = os.path.join("data", "raw")
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
    df = pd.DataFrame(rows).sort_values(["pipeline_id", "stage_order"])
    df["stage_order"] = df.groupby("pipeline_id").cumcount() + 1   
    return df
 
 
def transform_users(users: list, leads: pd.DataFrame) -> pd.DataFrame:
    active_ids = set(leads["responsible_user_id"].dropna())
    return pd.DataFrame([{
        "user_id": u["id"],
        "user_name": u["name"],
    } for u in users if u["id"] in active_ids])
 
 
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
    } for c in contacts])
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
 
    df = pd.DataFrame(rows)
 

    for col in ["created_at", "updated_at", "closed_at"]:
        df[col] = to_datetime(df[col])
 

    df["product"] = df["lead_name"].str.split(" — ").str[0]
 

    df["outcome"] = "Open"
    df.loc[df["status_id"] == WON_STATUS, "outcome"] = "Won"
    df.loc[df["status_id"] == LOST_STATUS, "outcome"] = "Lost"
 

    df["days_to_close"] = (df["closed_at"] - df["created_at"]).dt.days
 
    df["contact_id"] = df["contact_id"].astype("Int64")
    df["days_to_close"] = df["days_to_close"].astype("Int64")
    return df
 
 
# ============================== LOAD ==============================
def get_engine():
    url = (f"postgresql+psycopg2://{os.getenv('PG_USER')}:{os.getenv('PG_PASSWORD')}"
           f"@{os.getenv('PG_HOST', 'localhost')}:{os.getenv('PG_PORT', '5432')}"
           f"/{os.getenv('PG_DB')}")
    return create_engine(url)
 
 
def load(engine, tables: dict) -> None:
    for name, df in tables.items():
        df.to_sql(name, engine, if_exists="replace", index=False)
        print(f"  {name:<14} -> {len(df):>4} qator yuklandi")
 
    # Primary key'lar (Power BI'da bog'lanishlar uchun foydali)
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE dim_users    ADD PRIMARY KEY (user_id)"))
        conn.execute(text("ALTER TABLE dim_contacts ADD PRIMARY KEY (contact_id)"))
        conn.execute(text("ALTER TABLE fact_leads   ADD PRIMARY KEY (lead_id)"))
        conn.execute(text("ALTER TABLE dim_stages   ADD PRIMARY KEY (pipeline_id, status_id)"))
 
 
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
 