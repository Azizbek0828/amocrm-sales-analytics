"""Daily amoCRM refresh; task logs contain counts, never credentials."""
from datetime import timedelta

import pendulum
from airflow.sdk import DAG
from airflow.providers.standard.operators.bash import BashOperator


with DAG(
    dag_id="amocrm_sales_etl",
    description="amoCRM -> raw JSON -> PostgreSQL -> row-count verification",
    start_date=pendulum.datetime(2026, 1, 1, tz="Asia/Tashkent"),
    schedule="0 8 * * *",
    catchup=False,
    max_active_runs=1,
    is_paused_upon_creation=True,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=2)},
    tags=["amocrm", "etl", "postgresql"],
) as dag:
    def pipeline_task(task_id, module):
        return BashOperator(
            task_id=task_id,
            bash_command=f"python -u -m pipelines.{module}",
            cwd="/opt/amocrm",
            # All tasks use this run's files; previous runs cannot supply stale data.
            env={"AMO_RAW_DIR": "/opt/amocrm/data/raw/{{ run_id }}"},
            append_env=True,
            do_xcom_push=False,
            execution_timeout=timedelta(minutes=30),
        )

    extract = pipeline_task("extract", "extract")
    transform_load = pipeline_task("transform_load", "transform_load")
    verify_load = pipeline_task("verify_load", "verify_load")
    extract >> transform_load >> verify_load
