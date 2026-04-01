"""
Import cleaned official Gujarat Assembly election data into ElectionHistory.

Expected input:
    A CSV prepared from official ECI / CEO Gujarat sources, with one row per candidate.

Typical run:
    python scripts/import_official_assembly_data.py --file data/official/gujarat_assembly_official.csv --clear-years

This importer is intentionally stricter than the legacy importer:
    - validates required columns
    - supports only assembly-style candidate result rows
    - prints year-wise row/seat summaries after import
"""

import argparse
import os
import sys
from pathlib import Path

import django
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "election_system.settings")
django.setup()

from apps.prediction.models import ElectionHistory


REQUIRED_COLUMNS = [
    "year",
    "constituency",
    "candidate",
    "party",
    "votes",
    "vote_share",
    "won",
]

OPTIONAL_COLUMNS = [
    "assembly_no",
    "constituency_no",
    "constituency_type",
    "district",
    "state",
    "sub_region",
    "sex",
    "age",
    "candidate_type",
    "education",
    "profession_main",
    "profession_second",
    "party_id",
    "party_type",
    "valid_votes",
    "electors",
    "voter_turnout",
    "position",
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


def safe_int(value, default=None):
    try:
        if pd.isna(value) or value == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def safe_float(value, default=0.0):
    try:
        if pd.isna(value) or value == "":
            return default
        return round(float(value), 4)
    except (TypeError, ValueError):
        return default


def safe_bool(value, default=False):
    if isinstance(value, bool):
        return value
    if pd.isna(value):
        return default
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y"}:
        return True
    if text in {"0", "false", "no", "n"}:
        return False
    return default


def safe_str(value, default=""):
    if pd.isna(value):
        return default
    return str(value).strip()


def validate_columns(df: pd.DataFrame):
    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")


def import_csv(filepath: str, clear_years: bool = False):
    csv_path = Path(filepath)
    if not csv_path.is_absolute():
        csv_path = PROJECT_ROOT / csv_path

    df = pd.read_csv(csv_path, encoding="utf-8-sig", low_memory=False)
    validate_columns(df)

    df.columns = [column.strip() for column in df.columns]
    df = df.where(pd.notna(df), None)
    years = sorted({safe_int(value) for value in df["year"].tolist() if safe_int(value) is not None})

    print(f"Loaded {len(df):,} rows from {csv_path}")
    print(f"Years present: {years}")

    if clear_years and years:
        deleted, _ = ElectionHistory.objects.filter(year__in=years, state__iexact="Gujarat").delete()
        print(f"Cleared {deleted:,} existing Gujarat rows for years: {years}")

    created = 0
    updated = 0
    skipped = 0

    for _, row in df.iterrows():
        year = safe_int(row.get("year"))
        constituency = safe_str(row.get("constituency"))
        candidate = safe_str(row.get("candidate"))
        party = safe_str(row.get("party"))

        if not year or not constituency or not candidate or not party:
            skipped += 1
            continue

        defaults = {
            "assembly_no": safe_int(row.get("assembly_no")),
            "constituency_no": safe_int(row.get("constituency_no")),
            "constituency": constituency,
            "constituency_type": safe_str(row.get("constituency_type")),
            "district": safe_str(row.get("district")),
            "state": safe_str(row.get("state"), "Gujarat") or "Gujarat",
            "sub_region": safe_str(row.get("sub_region")),
            "candidate": candidate,
            "sex": safe_str(row.get("sex")),
            "age": safe_int(row.get("age")),
            "candidate_type": safe_str(row.get("candidate_type")),
            "education": safe_str(row.get("education")),
            "profession_main": safe_str(row.get("profession_main")),
            "profession_second": safe_str(row.get("profession_second")),
            "party": party,
            "party_id": safe_str(row.get("party_id")),
            "party_type": safe_str(row.get("party_type")),
            "votes": safe_int(row.get("votes"), 0) or 0,
            "valid_votes": safe_int(row.get("valid_votes"), 0) or 0,
            "electors": safe_int(row.get("electors"), 0) or 0,
            "vote_share": safe_float(row.get("vote_share"), 0.0),
            "voter_turnout": safe_float(row.get("voter_turnout"), 0.0),
            "position": safe_int(row.get("position")),
            "won": safe_bool(row.get("won"), False),
            "deposit_lost": safe_bool(row.get("deposit_lost"), False),
            "n_candidates": safe_int(row.get("n_candidates")),
            "margin": safe_int(row.get("margin")),
            "margin_pct": safe_float(row.get("margin_pct"), 0.0),
            "enop": safe_float(row.get("enop"), 0.0),
            "incumbent": safe_int(row.get("incumbent"), 0) or 0,
            "recontest": safe_int(row.get("recontest"), 0) or 0,
            "turncoat": safe_int(row.get("turncoat"), 0) or 0,
            "no_terms": safe_int(row.get("no_terms")),
            "same_constituency": safe_int(row.get("same_constituency")),
            "same_party": safe_int(row.get("same_party")),
            "last_party": safe_str(row.get("last_party")),
            "last_constituency": safe_str(row.get("last_constituency")),
            "last_poll": safe_int(row.get("last_poll")),
            "contested": safe_int(row.get("contested")),
        }

        obj, is_new = ElectionHistory.objects.update_or_create(
            year=year,
            constituency_no=defaults["constituency_no"],
            candidate=candidate,
            party=party,
            defaults=defaults,
        )
        if is_new:
            created += 1
        else:
            updated += 1

    print(f"\nImport complete")
    print(f"Created: {created:,}")
    print(f"Updated: {updated:,}")
    print(f"Skipped: {skipped:,}")

    for year in years:
        total = ElectionHistory.objects.filter(year=year, state__iexact="Gujarat").count()
        constituencies = ElectionHistory.objects.filter(year=year, state__iexact="Gujarat").values("constituency").distinct().count()
        winners = ElectionHistory.objects.filter(year=year, state__iexact="Gujarat", won=True).count()
        print(f"{year}: {total:,} rows | {constituencies} constituencies | {winners} winners")


def main():
    parser = argparse.ArgumentParser(description="Import cleaned official Gujarat assembly election CSV")
    parser.add_argument("--file", required=True, help="CSV path, e.g. data/official/gujarat_assembly_official.csv")
    parser.add_argument("--clear-years", action="store_true", help="Delete existing Gujarat rows for the imported years before loading")
    args = parser.parse_args()

    import_csv(args.file, clear_years=args.clear_years)


if __name__ == "__main__":
    main()
