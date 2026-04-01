"""
Prepare a clean Gujarat Assembly official dataset from year-wise raw folders.

What this script can do:
1. Create target year folders under data/official/raw
2. Merge cleaned CSV/XLSX files from those folders into one final CSV

Typical workflow:
    python scripts/prepare_official_dataset.py --init-dirs
    python scripts/prepare_official_dataset.py --merge

Expected per-year input:
- Place one or more cleaned CSV/XLSX files inside:
  data/official/raw/<year>/

Preferred schema:
- Use the same columns as data/official/gujarat_assembly_official_template.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OFFICIAL_DIR = PROJECT_ROOT / "data" / "official"
RAW_DIR = OFFICIAL_DIR / "raw"
OUTPUT_CSV = OFFICIAL_DIR / "gujarat_assembly_official.csv"

TARGET_YEARS = [
    1962, 1967, 1972, 1975, 1980, 1985, 1990,
    1995, 1998, 2002, 2007, 2012, 2017, 2022,
]

FINAL_COLUMNS = [
    "year",
    "assembly_no",
    "constituency_no",
    "constituency",
    "constituency_type",
    "district",
    "state",
    "sub_region",
    "candidate",
    "sex",
    "age",
    "candidate_type",
    "education",
    "profession_main",
    "profession_second",
    "party",
    "party_id",
    "party_type",
    "votes",
    "valid_votes",
    "electors",
    "vote_share",
    "voter_turnout",
    "position",
    "won",
    "deposit_lost",
    "n_candidates",
    "margin",
    "margin_pct",
    "enop",
    "incumbent",
    "recontest",
    "turncoat",
    "no_terms",
    "same_constituency",
    "same_party",
    "last_party",
    "last_constituency",
    "last_poll",
    "contested",
    "source_file",
    "source_notes",
]

COMMON_ALIASES = {
    "state_name": "state",
    "assembly_no": "assembly_no",
    "constituency_no": "constituency_no",
    "constituency_name": "constituency",
    "district_name": "district",
    "candidate_name": "candidate",
    "party_name": "party",
    "valid_votes_polled": "valid_votes",
    "turnout_percentage": "voter_turnout",
    "vote_share_percentage": "vote_share",
    "winner": "won",
}


def normalize_header(name: str) -> str:
    text = str(name).strip().lower()
    text = text.replace("%", "percentage")
    text = text.replace("/", "_")
    text = text.replace("-", "_")
    text = text.replace(" ", "_")
    text = "_".join(part for part in text.split("_") if part)
    return COMMON_ALIASES.get(text, text)


def init_dirs():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for year in TARGET_YEARS:
        year_dir = RAW_DIR / str(year)
        year_dir.mkdir(parents=True, exist_ok=True)
        keep = year_dir / ".gitkeep"
        if not keep.exists():
            keep.write_text("", encoding="utf-8")
    print(f"Initialized raw year folders under: {RAW_DIR}")


def load_table(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
    if path.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    raise ValueError(f"Unsupported file type: {path}")


def year_input_files(year: int) -> Iterable[Path]:
    year_dir = RAW_DIR / str(year)
    if not year_dir.exists():
        return []
    return sorted(
        file for file in year_dir.iterdir()
        if file.is_file() and file.suffix.lower() in {".csv", ".xlsx", ".xls"}
    )


def ensure_columns(df: pd.DataFrame, source_name: str) -> pd.DataFrame:
    df = df.copy()
    df.columns = [normalize_header(column) for column in df.columns]

    for column in FINAL_COLUMNS:
        if column not in df.columns:
            df[column] = None

    if "source_file" in df.columns:
        df["source_file"] = df["source_file"].fillna(source_name)
        df.loc[df["source_file"].astype(str).str.strip() == "", "source_file"] = source_name
    else:
        df["source_file"] = source_name

    if "state" in df.columns:
        df["state"] = df["state"].fillna("Gujarat")
        df.loc[df["state"].astype(str).str.strip() == "", "state"] = "Gujarat"
    else:
        df["state"] = "Gujarat"

    return df[FINAL_COLUMNS]


def merge_year_files():
    frames = []
    seen_files = []

    for year in TARGET_YEARS:
        for file in year_input_files(year):
            frame = load_table(file)
            frame = ensure_columns(frame, file.name)
            if "year" not in frame.columns or frame["year"].isna().all():
                frame["year"] = year
            frames.append(frame)
            seen_files.append(str(file.relative_to(PROJECT_ROOT)))

    if not frames:
        print("No CSV/XLSX files found in data/official/raw/<year>/ folders.")
        return

    merged = pd.concat(frames, ignore_index=True)
    merged = merged.drop_duplicates(subset=["year", "constituency_no", "candidate", "party"], keep="last")
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")

    print(f"Merged {len(seen_files)} files into: {OUTPUT_CSV}")
    print(f"Total rows: {len(merged):,}")
    print("Files used:")
    for file in seen_files:
        print(f"  - {file}")


def main():
    parser = argparse.ArgumentParser(description="Prepare official Gujarat Assembly dataset folders and merged CSV")
    parser.add_argument("--init-dirs", action="store_true", help="Create year-wise raw-data folders")
    parser.add_argument("--merge", action="store_true", help="Merge cleaned files from raw year folders into one official CSV")
    args = parser.parse_args()

    if args.init_dirs:
        init_dirs()
    if args.merge:
        merge_year_files()
    if not args.init_dirs and not args.merge:
        parser.print_help()


if __name__ == "__main__":
    main()
