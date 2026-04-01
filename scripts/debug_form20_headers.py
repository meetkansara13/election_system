import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))

from extract_form20_official_rows import (
    choose_header_lines_pypdf,
    choose_summary_page,
    extract_party_order,
    last_pages_payload,
    last_pages_pypdf_lines,
    rows_for_constituency,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--constituency-no", type=int, required=True)
    parser.add_argument("--pdf", required=True)
    args = parser.parse_args()

    pdf = Path(args.pdf)
    candidates = rows_for_constituency(args.year, args.constituency_no)
    payload = last_pages_pypdf_lines(pdf, 3)
    lines = choose_header_lines_pypdf(payload, len(candidates), candidates)
    print("HEADER:", lines)
    words, summary_lines = choose_summary_page(last_pages_payload(pdf, 3), len(candidates))
    print("PARTIES:", extract_party_order(summary_lines, candidates, len(candidates)))


if __name__ == "__main__":
    main()
