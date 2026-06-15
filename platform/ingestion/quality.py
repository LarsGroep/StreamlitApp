"""
Data quality checks: freshness, impossible jumps, coverage report.
Run after each ingestion cycle.

Usage:
    python -m ingestion.quality
"""

from datetime import datetime, timedelta

from rich.console import Console
from rich.table import Table
from sqlalchemy import func

from schema.database import get_session
from schema.models import Artist, MetricObservation

console = Console()

FRESHNESS_THRESHOLD_DAYS = 7
JUMP_FACTOR_THRESHOLD = 5.0   # flag if metric changes > 5× vs. previous
VOLUME_DROP_THRESHOLD = 0.5   # flag if < 50% of expected records


def check_freshness(session) -> list[dict]:
    cutoff = datetime.utcnow() - timedelta(days=FRESHNESS_THRESHOLD_DAYS)
    stale = []
    for source in ("lastfm", "partyflock", "ra", "chartmetric"):
        latest = (
            session.query(MetricObservation.artist_id, func.max(MetricObservation.observed_at))
            .filter_by(source=source)
            .group_by(MetricObservation.artist_id)
            .all()
        )
        stale_artists = [str(aid) for aid, ts in latest if ts < cutoff]
        if stale_artists:
            stale.append({"source": source, "stale_count": len(stale_artists), "artists": stale_artists[:5]})
    return stale


def check_impossible_jumps(session) -> list[dict]:
    flags = []
    subq = (
        session.query(
            MetricObservation.artist_id,
            MetricObservation.source,
            MetricObservation.metric,
            MetricObservation.value,
            MetricObservation.observed_at,
        )
        .order_by(
            MetricObservation.artist_id,
            MetricObservation.source,
            MetricObservation.metric,
            MetricObservation.observed_at,
        )
        .all()
    )

    prev: dict[tuple, float] = {}
    for artist_id, source, metric, value, observed_at in subq:
        key = (artist_id, source, metric)
        prev_val = prev.get(key)
        if prev_val and prev_val > 0 and value is not None:
            ratio = value / prev_val
            if ratio > JUMP_FACTOR_THRESHOLD or ratio < 1 / JUMP_FACTOR_THRESHOLD:
                flags.append({
                    "artist_id": str(artist_id),
                    "source": source,
                    "metric": metric,
                    "prev": prev_val,
                    "current": value,
                    "ratio": round(ratio, 2),
                    "at": observed_at.isoformat(),
                })
        if value is not None:
            prev[key] = value

    return flags


def coverage_report(session) -> dict:
    total = session.query(Artist).count()
    report = {"total_artists": total, "sources": {}}
    for source in ("lastfm", "partyflock", "ra", "chartmetric", "lofi_internal"):
        count = (
            session.query(func.count(func.distinct(MetricObservation.artist_id)))
            .filter_by(source=source)
            .scalar()
        )
        report["sources"][source] = {"artists_with_data": count, "coverage_pct": round(count / total * 100, 1) if total else 0}
    return report


def main():
    with get_session() as session:
        console.rule("[bold]Data Quality Report[/bold]")

        # Coverage
        cov = coverage_report(session)
        t = Table("Source", "Artists with data", "Coverage %")
        for source, stats in cov["sources"].items():
            t.add_row(source, str(stats["artists_with_data"]), f"{stats['coverage_pct']}%")
        console.print(f"\nTotal artists: {cov['total_artists']}")
        console.print(t)

        # Freshness
        stale = check_freshness(session)
        if stale:
            console.print(f"\n[yellow]Stale sources (>{FRESHNESS_THRESHOLD_DAYS}d since last update):[/yellow]")
            for s in stale:
                console.print(f"  {s['source']}: {s['stale_count']} artists stale. Examples: {s['artists'][:3]}")
        else:
            console.print("\n[green]All sources fresh.[/green]")

        # Impossible jumps
        jumps = check_impossible_jumps(session)
        if jumps:
            console.print(f"\n[red]Impossible jumps detected ({len(jumps)}):[/red]")
            for j in jumps[:10]:
                console.print(f"  {j['source']}/{j['metric']} @ {j['at']}: {j['prev']} → {j['current']} (×{j['ratio']})")
            if len(jumps) > 10:
                console.print(f"  ... and {len(jumps) - 10} more")
        else:
            console.print("\n[green]No impossible jumps.[/green]")


if __name__ == "__main__":
    main()
