"""Compare loaded row counts with this run's raw records, without changing data."""
from sqlalchemy import text
from pipelines.transform_load import (
    get_engine, read_raw, transform_contacts, transform_leads,
    transform_stages, transform_users,
)


def main():
    leads = transform_leads(read_raw("leads"))
    expected = {
        "fact_leads": len(leads),
        "dim_contacts": len(transform_contacts(read_raw("contacts"))),
        "dim_users": len(transform_users(read_raw("users"), leads)),
        "dim_stages": len(transform_stages(read_raw("pipelines"))),
    }
    engine = get_engine()
    try:
        with engine.connect() as conn:
            for table, expected_count in expected.items():
                actual = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
                if actual != expected_count:
                    raise ValueError(f"{table}: expected {expected_count}, found {actual}")
                print(f"{table}: {actual} rows OK")
        print("PostgreSQL yuklash tekshiruvi muvaffaqiyatli.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
