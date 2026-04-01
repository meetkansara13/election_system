"""
Generate a bulk download manifest for official CEO Gujarat Form-20 PDFs.

Usage:
    python scripts/generate_form20_manifest.py
"""

from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = PROJECT_ROOT / "data" / "official" / "download_manifest_bulk.json"


def build_entries():
    downloads = []

    for ac_no in range(1, 183):
        downloads.append({
            "year": 2007,
            "url": f"https://ceo.gujarat.gov.in/download/AE2007/AC2007_{ac_no:03d}.pdf",
            "filename": f"Form20_AC{ac_no:03d}_2007.pdf",
        })

    for ac_no in range(1, 183):
        downloads.append({
            "year": 2012,
            "url": f"https://ceo.gujarat.gov.in/download/Form20_2012/AC{ac_no:03d}.PDF",
            "filename": f"Form20_AC{ac_no:03d}_2012.pdf",
        })

    for ac_no in range(1, 183):
        downloads.append({
            "year": 2017,
            "url": f"https://ceo.gujarat.gov.in/download/Form20_2017/AC{ac_no:03d}.PDF",
            "filename": f"Form20_AC{ac_no:03d}_2017.pdf",
        })

    return {"downloads": downloads}


def main():
    manifest = build_entries()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)
    print(f"Wrote {len(manifest['downloads'])} downloads to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
