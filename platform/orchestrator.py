"""
Nightly pipeline runner. Runs all ingestion, quality checks, scoring in order.

Usage:
    python orchestrator.py
    python orchestrator.py --skip-scrape   # ingestion + scoring only (scrape ran separately)

Add to cron:
    0 3 * * * cd /path/to/platform && python orchestrator.py >> logs/nightly.log 2>&1
"""

import subprocess
import sys
from datetime import datetime
from pathlib import Path

import click

LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)


def step(name: str, fn):
    print(f"\n[{datetime.utcnow().isoformat()}] Starting: {name}")
    try:
        fn()
        print(f"[{datetime.utcnow().isoformat()}] Done: {name}")
    except Exception as e:
        print(f"[{datetime.utcnow().isoformat()}] FAILED: {name} — {e}")
        raise


@click.command()
@click.option("--skip-scrape", is_flag=True, default=False, help="Skip spider runs")
def main(skip_scrape: bool):
    from schema.database import init_db
    from ingestion.seed_artists import seed
    from ingestion.ingest_partyflock import main as ingest_pf
    from ingestion.ingest_lastfm import main as ingest_lfm
    from ingestion.ingest_ra import main as ingest_ra
    from ingestion.quality import main as quality_check
    from scoring.seed_frameworks import main as seed_fw
    from scoring.validation_events import detect_all
    from scoring.engine import run as run_scoring

    step("init_db", init_db)

    if not skip_scrape:
        step("scrapers", lambda: subprocess.run(
            ["make", "-C", "../ra-scraper-master", "partyflock", "ra", "lastfm"],
            check=True,
        ))

    step("seed_artists", seed)
    step("ingest_partyflock", ingest_pf)
    step("ingest_lastfm", ingest_lfm)
    step("ingest_ra", ingest_ra)
    step("quality_check", quality_check)
    step("seed_frameworks", lambda: seed_fw(standalone_mode=False, args=[], obj={}))
    step("validation_events", detect_all)
    step("scoring_engine", run_scoring)

    from ml.similarity import run as run_similarity
    step("lofi_similarity", lambda: run_similarity(top_n=50, threshold=100_000))

    from scoring.anomaly import run as run_anomaly
    from api.alerts import dispatch
    step("anomaly_detection", lambda: dispatch(run_anomaly()))

    print(f"\n[{datetime.utcnow().isoformat()}] Pipeline complete.")


if __name__ == "__main__":
    main()
