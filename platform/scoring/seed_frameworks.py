"""
Load sound framework config from YAML into the database.

Usage:
    python -m scoring.seed_frameworks
    python -m scoring.seed_frameworks --framework tech_house
"""

import uuid
from pathlib import Path

import click
import yaml

from schema.database import get_session
from schema.models import (
    FrameworkAgency, FrameworkArtist, FrameworkFestival,
    FrameworkLabel, FrameworkMedia, SoundFramework, Artist,
)
from resolution.resolver import resolve

FRAMEWORKS_DIR = Path(__file__).parent / "frameworks"


def load_framework(path: Path, session) -> SoundFramework:
    with path.open(encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    fw = session.query(SoundFramework).filter_by(name=cfg["name"]).first()
    if not fw:
        fw = SoundFramework(name=cfg["name"], genre=cfg.get("genre"))
        session.add(fw)
        session.flush()
        print(f"Created framework: {cfg['name']}")
    else:
        print(f"Framework exists: {cfg['name']} — refreshing config")
        session.query(FrameworkFestival).filter_by(framework_id=fw.id).delete()
        session.query(FrameworkLabel).filter_by(framework_id=fw.id).delete()
        session.query(FrameworkAgency).filter_by(framework_id=fw.id).delete()
        session.query(FrameworkMedia).filter_by(framework_id=fw.id).delete()
        session.query(FrameworkArtist).filter_by(framework_id=fw.id).delete()

    for item in cfg.get("festivals", []):
        session.add(FrameworkFestival(framework_id=fw.id, festival_name=item["name"], tier=item.get("tier")))

    for item in cfg.get("labels", []):
        session.add(FrameworkLabel(framework_id=fw.id, label_name=item["name"], tier=item.get("tier")))

    for item in cfg.get("agencies", []):
        session.add(FrameworkAgency(
            framework_id=fw.id,
            agency_name=item["name"],
            tier=item.get("tier"),
            score=item.get("score"),
        ))

    for item in cfg.get("media", []):
        session.add(FrameworkMedia(framework_id=fw.id, outlet_name=item["name"], tier=item.get("tier")))

    # Benchmark artists — resolve to canonical artist records
    for tier, names in cfg.get("benchmark_artists", {}).items():
        for name in names:
            artist_id, _ = resolve(session, name, source="framework_seed", auto_create=True)
            if artist_id:
                existing = session.query(FrameworkArtist).filter_by(
                    framework_id=fw.id, artist_id=artist_id
                ).first()
                if not existing:
                    session.add(FrameworkArtist(framework_id=fw.id, artist_id=artist_id, tier=tier))

    return fw


@click.command()
@click.option("--framework", default=None, help="Framework name to load (default: all)")
def main(framework):
    paths = list(FRAMEWORKS_DIR.glob("*.yaml"))
    if framework:
        paths = [p for p in paths if p.stem == framework]

    if not paths:
        print("No framework YAML files found.")
        return

    with get_session() as session:
        for path in paths:
            fw = load_framework(path, session)
            print(f"Seeded: {fw.name}")


if __name__ == "__main__":
    main()
