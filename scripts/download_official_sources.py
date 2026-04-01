"""
Download official Gujarat Assembly source files from a manifest.

Usage:
    python scripts/download_official_sources.py --manifest data/official/download_manifest.json

Manifest format:
{
  "downloads": [
    {
      "year": 2022,
      "url": "https://results.eci.gov.in/ResultAcGenDec2022/statewiseS069.htm",
      "filename": "eci_state_result_2022.html"
    }
  ]
}
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "official" / "raw"


def ensure_year_dir(year: int) -> Path:
    year_dir = RAW_DIR / str(year)
    year_dir.mkdir(parents=True, exist_ok=True)
    return year_dir


def infer_filename(url: str, fallback: str = "downloaded_file") -> str:
    name = url.rstrip("/").split("/")[-1].split("?")[0]
    return name or fallback


def download_one(item: dict) -> tuple[bool, str]:
    year = item.get("year")
    url = item.get("url")
    filename = item.get("filename")

    if not year or not url:
        return False, f"Skipped invalid item: {item}"

    year_dir = ensure_year_dir(int(year))
    target_name = filename or infer_filename(url)
    target_path = year_dir / target_name

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-IN,en;q=0.9",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Referer": "https://results.eci.gov.in/",
            "Upgrade-Insecure-Requests": "1",
        },
    )

    with urllib.request.urlopen(request, timeout=45) as response:
        content = response.read()
    target_path.write_bytes(content)
    return True, f"Downloaded {url} -> {target_path}"


def main():
    parser = argparse.ArgumentParser(description="Download official Gujarat Assembly source files from a manifest")
    parser.add_argument(
        "--manifest",
        default="data/official/download_manifest.json",
        help="Path to JSON manifest file",
    )
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    if not manifest_path.is_absolute():
        manifest_path = PROJECT_ROOT / manifest_path

    if not manifest_path.exists():
        print(f"Manifest not found: {manifest_path}")
        sys.exit(1)

    with manifest_path.open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)

    downloads = manifest.get("downloads", [])
    if not downloads:
        print("No downloads listed in manifest.")
        return

    success = 0
    failed = 0

    for item in downloads:
        try:
            ok, message = download_one(item)
            print(message)
            if ok:
                success += 1
            else:
                failed += 1
        except Exception as exc:
            failed += 1
            print(f"Failed for {item.get('url', 'unknown url')}: {exc}")

    print(f"\nDone. Success: {success} | Failed: {failed}")


if __name__ == "__main__":
    main()
