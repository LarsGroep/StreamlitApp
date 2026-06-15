"""
CLI for resolving artists in the resolution_queue.

Usage:
    python -m resolution.review_cli
    python -m resolution.review_cli --limit 20
"""

import uuid
import click
from rich.console import Console
from rich.table import Table

from schema.database import get_session
from schema.models import Artist, ArtistSourceMap, ResolutionQueue
from resolution.normalize import normalize

console = Console()


@click.command()
@click.option("--limit", default=50, help="Max items to review per session")
def main(limit: int):
    with get_session() as session:
        pending = (
            session.query(ResolutionQueue)
            .filter_by(status="pending")
            .order_by(ResolutionQueue.created_at)
            .limit(limit)
            .all()
        )

        if not pending:
            console.print("[green]Resolution queue is empty.[/green]")
            return

        console.print(f"[bold]{len(pending)} items to review[/bold]\n")

        for item in pending:
            console.rule(f"[bold]{item.external_name}[/bold]  (source: {item.source})")

            candidates = item.candidates or []
            if candidates:
                t = Table("#", "Artist", "Score", "ID")
                for i, c in enumerate(candidates, 1):
                    t.add_row(str(i), c["name"], f"{c['score']:.2f}", c["artist_id"])
                console.print(t)
            else:
                console.print("[yellow]No candidates found.[/yellow]")

            console.print(
                "[cyan]Options:[/cyan] [1-5] match candidate  "
                "[n] create new artist  [s] skip  [r] reject\n"
            )
            choice = click.prompt("Choice", default="s").strip().lower()

            if choice == "s":
                continue
            elif choice == "r":
                item.status = "rejected"
            elif choice == "n":
                name = click.prompt("Canonical name", default=item.external_name)
                artist = Artist(name=name)
                session.add(artist)
                session.flush()
                _link(session, item, artist.id)
            elif choice.isdigit() and 1 <= int(choice) <= len(candidates):
                artist_id = uuid.UUID(candidates[int(choice) - 1]["artist_id"])
                _link(session, item, artist_id)
            else:
                console.print("[yellow]Skipping.[/yellow]")

        total_resolved = sum(1 for i in pending if i.status == "resolved")
        console.print(f"\n[green]Resolved {total_resolved} / {len(pending)}[/green]")


def _link(session, item: ResolutionQueue, artist_id: uuid.UUID):
    from datetime import datetime
    item.status = "resolved"
    item.resolved_at = datetime.utcnow()
    item.resolved_artist_id = artist_id

    existing = (
        session.query(ArtistSourceMap)
        .filter_by(artist_id=artist_id, source=item.source)
        .first()
    )
    if not existing:
        session.add(ArtistSourceMap(
            artist_id=artist_id,
            source=item.source,
            external_id=item.external_id,
            confidence=0.9,
            resolved_at=datetime.utcnow(),
        ))
    console.print(f"[green]Linked to artist {artist_id}[/green]")


if __name__ == "__main__":
    main()
