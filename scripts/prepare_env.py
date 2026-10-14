"""Create local configuration without overwriting existing credentials."""
import base64
import os
from pathlib import Path
import secrets

ROOT = Path(__file__).resolve().parent.parent


def main():
    app_env = ROOT / ".env"
    if not app_env.exists():
        content = (ROOT / ".env.example").read_text(encoding="utf-8")
        app_env.write_text(content, encoding="utf-8")
    airflow_env = ROOT / "airflow" / ".env"
    content = airflow_env.read_text(encoding="utf-8-sig") if airflow_env.exists() else ""
    present = dict(line.split("=", 1) for line in content.splitlines()
                   if "=" in line and not line.lstrip().startswith("#"))
    defaults = {
        "AIRFLOW_UID": "50000",
        "COMPOSE_PROJECT_NAME": "amocrm_airflow",
        "AIRFLOW_PORT": "8081",
        "FERNET_KEY": base64.urlsafe_b64encode(os.urandom(32)).decode(),
        "AIRFLOW__API_AUTH__JWT_SECRET": secrets.token_urlsafe(32),
    }
    for key, value in defaults.items():
        old = present.get(key, "")
        if not old or old.startswith("replace_with_"):
            content = "\n".join(line for line in content.splitlines()
                                 if not line.startswith(key + "="))
            content = content.rstrip() + f"\n{key}={value}\n"
    airflow_env.write_text(content.lstrip("\n"), encoding="utf-8")
    (ROOT / "data" / "raw").mkdir(parents=True, exist_ok=True)
    for folder in ["dags", "logs", "config"]:
        (ROOT / "airflow" / folder).mkdir(parents=True, exist_ok=True)
    print("Local .env files ready. Existing credentials preserved; secrets not printed.")
    print("Use your Windows PostgreSQL PG_PORT, PG_DB, PG_USER and PG_PASSWORD in the root .env.")


if __name__ == "__main__":
    main()
