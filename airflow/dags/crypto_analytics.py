"""Hourly analytics refresh: Coinbase candle backfill -> trade-gap repair -> dbt build.

The backfill steps run the project's own venv (venv/bin/python), and Cosmos calls the project's
dbt (venv/bin/dbt), so this Airflow venv only needs Airflow and Cosmos. Cosmos renders every dbt
model as its own run task followed by its tests, so a failing test points at the model that broke.
"""

from datetime import datetime, timedelta
from pathlib import Path

from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG
from cosmos import DbtTaskGroup, ExecutionConfig, ProfileConfig, ProjectConfig, RenderConfig
from cosmos.constants import TestBehavior

REPO = Path(__file__).resolve().parents[2]
PYTHON = REPO / "venv" / "bin" / "python"
DBT_PROJECT = REPO / "analytics"

with DAG(
    dag_id="crypto_analytics",
    schedule="@hourly",
    start_date=datetime(2026, 9, 24),
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=5)},
    tags=["analytics", "dbt"],
    doc_md=__doc__,
):
    backfill_candles = BashOperator(
        task_id="backfill_candles",
        bash_command=f"cd {REPO} && {PYTHON} -m src.backfill candles",
    )
    repair_trade_gaps = BashOperator(
        task_id="repair_trade_gaps",
        bash_command=f"cd {REPO} && {PYTHON} -m src.backfill gaps",
    )
    dbt = DbtTaskGroup(
        group_id="dbt",
        project_config=ProjectConfig(DBT_PROJECT),
        profile_config=ProfileConfig(
            profile_name="crypto_analytics",
            target_name="dev",
            profiles_yml_filepath=DBT_PROJECT / "profiles.yml",
        ),
        execution_config=ExecutionConfig(dbt_executable_path=str(REPO / "venv" / "bin" / "dbt")),
        render_config=RenderConfig(test_behavior=TestBehavior.AFTER_EACH),
    )

    backfill_candles >> repair_trade_gaps >> dbt
