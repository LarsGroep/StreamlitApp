"""
Framework YAML Builder.

Reads the scraped JSONL outputs and generates summary reports + YAML suggestions
for populating or updating sound framework configs.

Outputs (to stdout / files in ../platform/scoring/frameworks/):
  - Per-framework: top N artists by appearance count across all scraped sources
  - Per-framework: top labels by release frequency
  - Per-framework: most-active shows (from Mixcloud episode data)

Usage:
    python build_frameworks.py                    # print summaries to stdout
    python build_frameworks.py --update-yamls     # patch framework YAMLs with suggestions
    python build_frameworks.py --framework tech_house --top 30
"""

import json
import re
from collections import defaultdict
from pathlib import Path

import click
import yaml

SCRAPED_DIR = Path(__file__).parent / "scraper"
FRAMEWORKS_DIR = Path(__file__).parent.parent / "platform" / "scoring" / "frameworks"
JSONL_FILES = {
    "beatport_charts":       SCRAPED_DIR / "BeatportChartItem.jsonl",
    "beatport_labels":       SCRAPED_DIR / "BeatportLabelArtistItem.jsonl",
    "mixcloud":              SCRAPED_DIR / "MixcloudEpisodeItem.jsonl",
    "ra_genre":              SCRAPED_DIR / "RAGenreArtistItem.jsonl",
    "ra_labels":             SCRAPED_DIR / "RALabelArtistItem.jsonl",
}


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return rows


def build_artist_counts(framework: str | None = None) -> dict[str, dict[str, int]]:
    """
    Returns {framework_name: {artist_name: score}}.
    Score = weighted sum of appearances across sources:
      - Beatport chart rank: 101 - rank (top = 100pts, 100th = 1pt)
      - Beatport label release: 3 pts per release (capped at 15)
      - RA genre events: 2 pts per event
      - RA label release: 3 pts per release (capped at 15)
      - Mixcloud featured: 5 pts per episode appearance
    """
    scores: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    # Beatport charts
    for row in _read_jsonl(JSONL_FILES["beatport_charts"]):
        fw = row.get("genre_id_to_framework") or _genre_to_framework(row.get("genre", ""))
        if framework and fw != framework:
            continue
        rank = row.get("rank") or 100
        pts = max(1, 101 - rank)
        for artist in row.get("artists") or []:
            scores[fw][artist] += pts

    # Beatport label artists
    for row in _read_jsonl(JSONL_FILES["beatport_labels"]):
        fw = row.get("framework") or _label_to_framework(row.get("label_slug", ""))
        if framework and fw != framework:
            continue
        count = min(row.get("release_count") or 1, 5)
        scores[fw][row["artist_name"]] += count * 3

    # RA genre artists
    for row in _read_jsonl(JSONL_FILES["ra_genre"]):
        fw = _tag_to_framework(row.get("genre_tag", ""))
        if framework and fw != framework:
            continue
        count = min(row.get("event_count") or 1, 10)
        scores[fw][row["artist_name"]] += count * 2

    # RA label artists
    for row in _read_jsonl(JSONL_FILES["ra_labels"]):
        fw = row.get("framework") or _label_to_framework(row.get("label_slug", ""))
        if framework and fw != framework:
            continue
        count = min(row.get("release_count") or 1, 5)
        scores[fw][row["artist_name"]] += count * 3

    # Mixcloud featured artists
    for row in _read_jsonl(JSONL_FILES["mixcloud"]):
        fw = row.get("framework") or "all"
        fws = list(scores.keys()) if fw == "all" else [fw]
        if framework and framework not in fws and fw != framework:
            continue
        for artist in row.get("featured_artists") or []:
            for f in fws:
                scores[f][artist] += 5

    return {k: dict(v) for k, v in scores.items()}


def _genre_to_framework(genre_name: str) -> str:
    g = genre_name.lower()
    if "melodic" in g or "progressive house" in g or "organic" in g:
        return "melodic"
    if "afro" in g:
        return "afro_house"
    if "uk garage" in g or "trance" in g or "bounce" in g:
        return "bounce_trance_ukg"
    if "hypnotic" in g or "raw" in g or "industrial" in g:
        return "new_school_techno"
    if "techno" in g or "peak time" in g or "driving" in g:
        return "progressive_techno"
    if "leftfield" in g or "experimental" in g:
        return "leftfield_house_techno"
    return "tech_house"


_TAG_MAP = {
    "tech-house": "tech_house",
    "house": "tech_house",
    "deep-house": "tech_house",
    "melodic-house-techno": "melodic",
    "melodic-techno": "melodic",
    "techno": "progressive_techno",
    "industrial-techno": "new_school_techno",
    "hypnotic-techno": "new_school_techno",
    "afro-house": "afro_house",
    "afrobeat": "afro_house",
    "uk-garage": "bounce_trance_ukg",
    "trance": "bounce_trance_ukg",
    "leftfield-house": "leftfield_house_techno",
    "experimental": "leftfield_house_techno",
}

_LABEL_MAP = {
    # tech_house
    "solid-grooves-records": "tech_house",
    "piv-records":           "tech_house",
    "hot-creations":         "tech_house",
    "cuttin-headz":          "tech_house",
    "up-the-stuss":          "tech_house",
    "eastenderz":            "tech_house",
    "revival-new-york":      "tech_house",
    "heavy-house-society":   "tech_house",
    "cecille-records":       "tech_house",
    "circoloco-records":     "tech_house",
    "no-art":                "tech_house",
    # melodic
    "afterlife":             "melodic",
    "diynamic":              "melodic",
    "diynamic-music":        "melodic",   # legacy slug
    "innervisions":          "melodic",
    "life-and-death":        "melodic",
    "kompakt":               "melodic",
    # progressive_techno
    "drumcode":              "progressive_techno",
    "tronic":                "progressive_techno",
    "soma-records":          "progressive_techno",
    # new_school_techno
    "repitch-recordings":    "new_school_techno",
    "stroboscopic-artefacts":"new_school_techno",
    "horizontal-ground":     "new_school_techno",
    # afro_house
    "soulistic-music":       "afro_house",
    "offering-recordings":   "afro_house",
    "atjazz-record-company": "afro_house",
    # leftfield_house_techno
    "fabric-records":        "leftfield_house_techno",
    "rekids":                "leftfield_house_techno",
    "numbers":               "leftfield_house_techno",
    "hemlock-recordings":    "leftfield_house_techno",
    # bounce_trance_ukg
    "toolroom":              "bounce_trance_ukg",
    "magnetic-island":       "bounce_trance_ukg",
}


def _tag_to_framework(tag: str) -> str:
    return _TAG_MAP.get(tag, "tech_house")


def _label_to_framework(label_slug: str) -> str:
    return _LABEL_MAP.get(label_slug, "tech_house")


def _top_artists(scores: dict[str, int], n: int) -> list[tuple[str, int]]:
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)[:n]


@click.command()
@click.option("--framework", default=None, help="Filter to one framework (e.g. tech_house)")
@click.option("--top", default=20, type=int, help="Number of top artists to show per framework")
@click.option("--update-yamls", is_flag=True, default=False,
              help="Add 'suggested_benchmark_artists' section to framework YAMLs")
def main(framework: str | None, top: int, update_yamls: bool):
    counts = build_artist_counts(framework)

    if not counts:
        click.echo("No data found. Run the spiders first: make all")
        return

    for fw, scores in sorted(counts.items()):
        if framework and fw != framework:
            continue
        top_artists = _top_artists(scores, top)
        click.echo(f"\n{'='*60}")
        click.echo(f"  {fw}  --  top {top} artists by cross-source score")
        click.echo(f"{'='*60}")
        for i, (artist, score) in enumerate(top_artists, 1):
            click.echo(f"  {i:3d}. {artist:<35} score={score}")

        if update_yamls:
            yaml_path = FRAMEWORKS_DIR / f"{fw}.yaml"
            if yaml_path.exists():
                with open(yaml_path, encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                data["suggested_benchmark_artists"] = [a for a, _ in top_artists]
                with open(yaml_path, "w", encoding="utf-8") as f:
                    yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
                click.echo(f"  -> Updated {yaml_path}")
            else:
                click.echo(f"  WARNING: No YAML found at {yaml_path} -- skipping update")

    # Mixcloud show activity summary
    mixcloud_rows = _read_jsonl(JSONL_FILES["mixcloud"])
    if mixcloud_rows:
        show_counts: dict[str, int] = defaultdict(int)
        for row in mixcloud_rows:
            show_counts[row.get("show_name", row.get("show_username", "?"))] += 1
        click.echo(f"\n{'='*60}")
        click.echo("  Mixcloud show episode counts")
        click.echo(f"{'='*60}")
        for show, count in sorted(show_counts.items(), key=lambda x: x[1], reverse=True):
            click.echo(f"  {show:<40} {count} episodes")


if __name__ == "__main__":
    main()
