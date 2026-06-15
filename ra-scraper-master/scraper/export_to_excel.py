"""
Converts all JSONL output files in this directory to a single Excel file.
Each JSONL file becomes its own sheet. Run after scraping:
    python export_to_excel.py
"""

import json
from datetime import datetime
from pathlib import Path

import pandas as pd

HERE = Path(__file__).parent

SHEET_NAMES = {
    "EventItem": "RA Events",
    "EventLineupItem": "RA Lineups",
    "PartyflockArtistItem": "Partyflock Artists",
    "PartyflockEventItem": "Partyflock Events",
    "PartyflockLineupItem": "Partyflock Lineups",
    "FestivalLineupItem": "Festival Lineups",
}

LASTFM_SNAPSHOT = HERE / "lastfm" / "LastFMSnapshot.jsonl"

# List columns that contain lists and should be joined to a string
LIST_COLUMNS = {"lineup", "genres", "tags", "similar", "pf_genres"}


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _autosize(ws):
    for col in ws.columns:
        max_len = max((len(str(c.value)) for c in col if c.value), default=10)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 60)


def main():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = HERE / f"scraper_export_{timestamp}.xlsx"

    found_any = False
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        # JSONL sheets
        for stem, sheet_name in SHEET_NAMES.items():
            jsonl_path = HERE / f"{stem}.jsonl"
            if not jsonl_path.exists():
                print(f"  skip  {stem}.jsonl (not found)")
                continue

            rows = load_jsonl(jsonl_path)
            if not rows:
                print(f"  skip  {stem}.jsonl (empty)")
                continue

            df = pd.DataFrame(rows)

            for col in LIST_COLUMNS:
                if col in df.columns:
                    df[col] = df[col].apply(
                        lambda v: ", ".join(v) if isinstance(v, list) else v
                    )

            df.to_excel(writer, sheet_name=sheet_name, index=False)
            _autosize(writer.sheets[sheet_name])
            print(f"  wrote {len(df):>5} rows  ->  sheet '{sheet_name}'")
            found_any = True

        # LastFM snapshots (now in lastfm/ subfolder)
        if LASTFM_SNAPSHOT.exists():
            lfm_rows = load_jsonl(LASTFM_SNAPSHOT)
            if lfm_rows:
                df_lfm = pd.DataFrame(lfm_rows)
                for col in LIST_COLUMNS:
                    if col in df_lfm.columns:
                        df_lfm[col] = df_lfm[col].apply(
                            lambda v: ", ".join(v) if isinstance(v, list) else v
                        )
                df_lfm.to_excel(writer, sheet_name="LastFM Stats", index=False)
                _autosize(writer.sheets["LastFM Stats"])
                print(f"  wrote {len(df_lfm):>5} rows  ->  sheet 'LastFM Stats'")
                found_any = True

        # features.csv as its own sheet
        features_path = HERE / "features.csv"
        if features_path.exists():
            df_feat = pd.read_csv(features_path, encoding="utf-8")
            df_feat.to_excel(writer, sheet_name="IF Features", index=False)
            _autosize(writer.sheets["IF Features"])
            print(f"  wrote {len(df_feat):>5} rows  ->  sheet 'IF Features'")
            found_any = True

    if found_any:
        print(f"\nSaved: {out_path}")
    else:
        print("No data files found — run scrapy crawl first.")
        out_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
