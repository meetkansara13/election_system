from __future__ import annotations

import argparse
import difflib
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import django
import pandas as pd
import pdfplumber
from pypdf import PdfReader


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "election_system.settings")
django.setup()

from apps.prediction.models import ElectionHistory


RAW_DIR = PROJECT_ROOT / "data" / "official" / "raw"
OUTPUT_DIR = PROJECT_ROOT / "data" / "official" / "cleaned"

SKIP_WORDS = {
    "POLLING", "STATION", "VALID", "REJECTED", "TENDERED", "VOTES", "VOTE",
    "TOTAL", "OF", "NO", "NO.", "NOOF", "SERIAL",
    "ELECTORS", "IN", "CAST", "FAVOUR", "CONDUCT", "ELECTION", "RULES",
    "ORDER", "FORM", "SEE", "RULE", "FINAL", "RESULT", "SHEET", "LEGISLATIVE",
    "ASSEMBLY", "PARLIAMENTRYCONSTITUENCY", "PART", "ROUNDWISE", "NAME",
    "SEGMENT", "TO", "BE", "USED", "FOR", "RECORDING", "AT", "OTHER", "THAN",
    "NOTIFIED", "POLLINGSTATIONS", "BOTH", "PARLIAMENTARY", "AND",
    "SR", "SRNO", "NUMBER", "TENDERE", "TENDERED", "POLLINGSTATIONS",
    "NOOF", "NOOFVALID", "NOOFREJECTED", "NOOFTENDERED",
}


@dataclass
class CandidateMeta:
    candidate: str
    norm_candidate: str
    row: ElectionHistory


def normalize_name(value: str) -> str:
    text = (value or "").upper()
    text = re.sub(r"[^A-Z0-9 ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def candidate_similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, normalize_name(a), normalize_name(b)).ratio()


def constituency_no_from_filename(pdf_path: Path) -> int:
    match = re.search(r"AC0*([0-9]{1,3})", pdf_path.stem, re.IGNORECASE)
    if not match:
        raise ValueError(f"Could not parse constituency number from filename: {pdf_path.name}")
    return int(match.group(1))


def rows_for_constituency(year: int, constituency_no: int) -> list[CandidateMeta]:
    rows = list(
        ElectionHistory.objects.filter(year=year, constituency_no=constituency_no, state__iexact="Gujarat")
        .order_by("candidate")
    )
    if not rows:
        raise ValueError(f"No existing DB metadata for year={year}, constituency_no={constituency_no}")
    return [CandidateMeta(row.candidate, normalize_name(row.candidate), row) for row in rows]


def last_pages_pypdf_lines(pdf_path: Path, pages_from_end: int = 3) -> list[tuple[int, list[str]]]:
    reader = PdfReader(str(pdf_path))
    start = max(len(reader.pages) - pages_from_end, 0)
    payload = []
    for page_index in range(start, len(reader.pages)):
        text = reader.pages[page_index].extract_text() or ""
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        payload.append((page_index, lines))
    return payload


def last_pages_payload(pdf_path: Path, pages_from_end: int = 3) -> list[tuple[int, list[dict], list[str]]]:
    with pdfplumber.open(str(pdf_path)) as pdf:
        start = max(len(pdf.pages) - pages_from_end, 0)
        payload = []
        for page_index in range(start, len(pdf.pages)):
            page = pdf.pages[page_index]
            words = page.extract_words(use_text_flow=False, keep_blank_chars=False)
            text = page.extract_text() or ""
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            payload.append((page_index, words, lines))
    return payload


def is_serial_numbers_line(line: str, n_candidates: int) -> bool:
    values = [int(value) for value in re.findall(r"\d+", line)]
    if len(values) < n_candidates:
        return False
    filtered = [value for value in values if 1 <= value <= n_candidates]
    expected = list(range(1, min(n_candidates, len(filtered)) + 1))
    return filtered[: len(expected)] == expected


def choose_summary_page(payload: list[tuple[int, list[dict], list[str]]], n_candidates: int) -> tuple[list[dict], list[str]]:
    best_score = -1
    best_page = None
    for _, words, lines in payload:
        joined = " ".join(lines).upper()
        score = 0
        if "TOTAL FOR A.C." in joined:
            score += 8
        if "TOTAL NO. OF VOTES" in joined:
            score += 6
        if "RECORDED AT" in joined:
            score += 5
        if "POSTAL VOTES" in joined or "POSTAL BALLOT" in joined:
            score += 3
        if any(is_serial_numbers_line(line, n_candidates) for line in lines):
            score += 2
        if score > best_score:
            best_score = score
            best_page = (words, lines)
    if best_page is None:
        raise ValueError("Could not choose a usable summary page from the last pages")
    return best_page


def choose_summary_lines_pypdf(payload: list[tuple[int, list[str]]], n_candidates: int) -> list[str]:
    best_score = -1
    best_lines = None
    for _, lines in payload:
        joined = " ".join(lines).upper()
        score = 0
        if "TOTAL FOR A.C." in joined:
            score += 8
        if "TOTAL VOTES POLLED" in joined or "TOTAL NO. OF VOTES" in joined:
            score += 6
        if "POSTAL VOTES" in joined or "POSTAL BALLOT" in joined:
            score += 3
        if any(is_serial_numbers_line(line, n_candidates) for line in lines):
            score += 2
        if score > best_score:
            best_score = score
            best_lines = lines
    if best_lines is None:
        raise ValueError("Could not choose a usable pypdf summary page from the last pages")
    return best_lines


def choose_header_lines_pypdf(payload: list[tuple[int, list[str]]], n_candidates: int, candidates: list[CandidateMeta]) -> list[str]:
    best: list[str] = []
    for _, lines in payload:
        header = extract_header_lines_pypdf(lines, n_candidates, candidates)
        if len(header) > len(best):
            best = header
    return best


def find_serial_row(words: list[dict], n_candidates: int) -> list[dict]:
    candidates = [w for w in words if re.fullmatch(r"\d+", w["text"])]
    grouped: dict[int, list[dict]] = {}
    for word in candidates:
        key = round(word["top"])
        grouped.setdefault(key, []).append(word)

    best_row = []
    for _, row_words in grouped.items():
        row_words = sorted(row_words, key=lambda item: item["x0"])
        values = [int(word["text"]) for word in row_words if int(word["text"]) <= n_candidates]
        if values[:min(3, n_candidates)] == list(range(1, min(3, n_candidates) + 1)) and len(values) >= n_candidates:
            best_row = row_words
            break
        if len(values) > len(best_row):
            best_row = row_words

    if len(best_row) < n_candidates:
        raise ValueError("Could not find a usable candidate serial row on the last PDF page")
    return sorted(best_row, key=lambda item: item["x0"])[:n_candidates]


def extract_names_from_columns(words: list[dict], serial_words: list[dict]) -> list[str]:
    serial_top = min(word["top"] for word in serial_words)
    left_edges = []
    right_edges = []
    for idx, word in enumerate(serial_words):
        if idx == 0:
            left = word["x0"] - 35
        else:
            left = (serial_words[idx - 1]["x0"] + word["x0"]) / 2
        if idx == len(serial_words) - 1:
            right = word["x1"] + 45
        else:
            right = (word["x1"] + serial_words[idx + 1]["x0"]) / 2
        left_edges.append(left)
        right_edges.append(right)

    header_words = [
        word for word in words
        if serial_top - 80 <= word["top"] <= serial_top - 2
    ]

    names = []
    for left, right in zip(left_edges, right_edges):
        bucket = [
            word for word in header_words
            if left <= ((word["x0"] + word["x1"]) / 2) <= right
            and normalize_name(word["text"]) not in SKIP_WORDS
            and len(normalize_name(word["text"])) > 1
        ]
        bucket.sort(key=lambda item: (round(item["top"]), item["x0"]))
        name = " ".join(word["text"] for word in bucket)
        names.append(re.sub(r"\s+", " ", name).strip())
    return names


def extract_header_lines_pypdf(lines: list[str], n_candidates: int, candidates: list[CandidateMeta]) -> list[str]:
    stop_markers = ("FORM 20", "FORM-20", "FINAL RESULT SHEET", "NAME OF THE ASSEMBLY", "GUJARAT LEGISLATIVE", "PART I")
    known_parties = {normalize_name(candidate.row.party) for candidate in candidates}
    header = []
    for line in lines:
        upper = line.upper()
        if any(marker in upper for marker in stop_markers):
            break
        if re.fullmatch(r"[\d\s/().-]+", line):
            continue
        if is_serial_numbers_line(line, n_candidates):
            continue
        tokens = [normalize_name(token) for token in re.split(r"\s+", line)]
        meaningful = [token for token in tokens if token and token not in SKIP_WORDS]
        if not meaningful:
            continue
        if any(token.startswith("NOOF") for token in meaningful):
            continue
        if all(token in known_parties for token in meaningful if token):
            continue
        header.append(line.strip())
    if header:
        return header

    collecting = False
    alt_header = []
    for line in lines:
        upper = line.upper()
        if "TENDERED" in upper:
            collecting = True
            continue
        if not collecting:
            continue
        if "SR." in upper or "POLLING" in upper or "VALID VOTES CAST" in upper or "NO.OF VALID" in upper:
            break
        if re.fullmatch(r"[\d\s/().-]+", line):
            continue
        tokens = [normalize_name(token) for token in re.split(r"\s+", line)]
        meaningful = [token for token in tokens if token and token not in SKIP_WORDS]
        if not meaningful:
            continue
        if any(token.startswith("NOOF") for token in meaningful):
            continue
        if all(token in known_parties for token in meaningful if token):
            continue
        alt_header.append(line.strip())
    return alt_header


def segment_candidate_headers(header_lines: list[str], candidates: list[CandidateMeta]) -> list[CandidateMeta]:
    target = len(candidates)
    used: set[str] = set()
    ordered: list[CandidateMeta] = []
    index = 0

    while index < len(header_lines) and len(ordered) < target:
        remaining_groups = target - len(ordered)
        remaining_lines = len(header_lines) - index
        best_score = -1.0
        best_span = None
        best_chunk = None
        best_candidate = None

        for span in range(1, min(4, remaining_lines + 1)):
            lines_after = remaining_lines - span
            min_after = remaining_groups - 1
            max_after = (remaining_groups - 1) * 4
            if lines_after < min_after or lines_after > max_after:
                continue

            chunk = " ".join(header_lines[index:index + span]).strip()
            if not chunk:
                continue

            for candidate in candidates:
                if candidate.norm_candidate in used:
                    continue
                score = candidate_similarity(chunk, candidate.candidate)
                if (
                    score > best_score
                    or (score == best_score and (best_span is None or span < best_span))
                ):
                    best_score = score
                    best_span = span
                    best_chunk = chunk
                    best_candidate = candidate

        if best_candidate is None or best_span is None or best_chunk is None:
            raise ValueError(f"Failed to segment candidate headers near line {index + 1}")

        if best_score < 0.5:
            raise ValueError(f"Weak pypdf candidate-name match for chunk '{best_chunk}' -> '{best_candidate.candidate}' ({best_score:.2f})")
        ordered.append(best_candidate)
        used.add(best_candidate.norm_candidate)
        index += best_span

    if len(ordered) != target:
        raise ValueError(f"Pypdf header segmentation incomplete: matched {len(ordered)} of {target} candidates")
    return ordered


def extract_party_order(lines: list[str], candidates: list[CandidateMeta], n_candidates: int) -> list[str]:
    known_parties = {normalize_name(candidate.row.party) for candidate in candidates}
    best: list[str] = []
    for line in lines:
        if is_serial_numbers_line(line, n_candidates):
            break
        raw_tokens = re.split(r"\s+", line.strip())
        merged = []
        index = 0
        while index < len(raw_tokens):
            token = raw_tokens[index]
            if index + 1 < len(raw_tokens) and raw_tokens[index + 1].startswith("("):
                token = token + " " + raw_tokens[index + 1]
                index += 1
            merged.append(token)
            index += 1
        filtered = [normalize_name(token) for token in merged if normalize_name(token) in known_parties]
        if len(filtered) > len(best):
            best = filtered
    return best[:n_candidates]


def match_extracted_names(extracted_names: list[str], candidates: list[CandidateMeta], party_order: list[str] | None = None) -> list[CandidateMeta]:
    used: set[str] = set()
    ordered = []
    for idx, extracted in enumerate(extracted_names):
        norm_extracted = normalize_name(extracted)
        best_score = -1.0
        best_candidate = None
        expected_party = party_order[idx] if party_order and idx < len(party_order) else None
        for candidate in candidates:
            if candidate.norm_candidate in used:
                continue
            if expected_party and normalize_name(candidate.row.party) != expected_party:
                continue
            score = difflib.SequenceMatcher(None, norm_extracted, candidate.norm_candidate).ratio()
            if score > best_score:
                best_score = score
                best_candidate = candidate
        if best_candidate is None and expected_party:
            party_matches = [
                candidate for candidate in candidates
                if candidate.norm_candidate not in used and normalize_name(candidate.row.party) == expected_party
            ]
            if len(party_matches) == 1:
                best_candidate = party_matches[0]
                best_score = 0.4
        if best_candidate is None or best_score < 0.4:
            raise ValueError(f"Could not confidently match extracted candidate header '{extracted}'")
        used.add(best_candidate.norm_candidate)
        ordered.append(best_candidate)
    return ordered


def order_candidates_from_party_order(candidates: list[CandidateMeta], party_order: list[str]) -> list[CandidateMeta] | None:
    ordered = []
    used: set[str] = set()
    for party in party_order:
        matches = [
            candidate for candidate in candidates
            if candidate.norm_candidate not in used and normalize_name(candidate.row.party) == party
        ]
        if len(matches) != 1:
            return None
        ordered.append(matches[0])
        used.add(matches[0].norm_candidate)
    return ordered if len(ordered) == len(candidates) else None


def numbers_from_line(line: str) -> list[int]:
    return [int(value) for value in re.findall(r"\d+", line)]


def extract_summary_values(lines: list[str], n_candidates: int) -> tuple[list[int], int, int]:
    electors = 0
    candidate_blobs: list[tuple[int, str]] = []
    for idx, line in enumerate(lines):
        upper = line.upper()
        if "TOTAL NO. OF ELECTORS" in upper:
            nums = numbers_from_line(line)
            if nums:
                electors = nums[-1]
        if "TOTAL FOR A.C." in upper:
            candidate_blobs.append((10, " ".join(lines[max(0, idx - 1):idx + 4])))
        if "RECORDED AT" in upper or "TOTAL VOTES POLLED" in upper:
            candidate_blobs.append((8, " ".join(lines[max(0, idx - 1):idx + 5])))
        if upper.startswith("TOTAL ") and "ELECTORS" not in upper and idx + 1 < len(lines):
            candidate_blobs.append((5, " ".join(lines[max(0, idx - 1):idx + 4])))

    if not candidate_blobs:
        raise ValueError("Could not find final totals row on the last page")

    best_values = None
    best_score = (-1, -1)
    for weight, blob in candidate_blobs:
        values = numbers_from_line(blob)
        count = len(values)
        if count >= n_candidates + 1:
            score = (weight, count)
            if score > best_score:
                best_score = score
                best_values = values

    if best_values is None:
        fallback = numbers_from_line(candidate_blobs[-1][1])
        raise ValueError(f"Unexpected total-votes payload: {fallback}")

    values = best_values
    candidate_votes = values[:n_candidates]
    valid_votes = values[n_candidates]
    return candidate_votes, valid_votes, electors


def resolve_ordered_candidates(
    pdf_words: list[dict],
    pdf_lines: list[str],
    pypdf_lines: list[str],
    candidates: list[CandidateMeta],
) -> list[CandidateMeta]:
    serial_words = find_serial_row(pdf_words, len(candidates))
    extracted_names = extract_names_from_columns(pdf_words, serial_words)
    party_order = extract_party_order(pdf_lines, candidates, len(candidates))
    try:
        return match_extracted_names(extracted_names, candidates, party_order=party_order)
    except Exception:
        if party_order and len(party_order) == len(candidates):
            party_only = order_candidates_from_party_order(candidates, party_order)
            if party_only:
                return party_only
        header_lines = extract_header_lines_pypdf(pypdf_lines, len(candidates), candidates)
        return segment_candidate_headers(header_lines, candidates)


def extract_one_pdf(year: int, pdf_path: Path) -> list[dict]:
    constituency_no = constituency_no_from_filename(pdf_path)
    candidates = rows_for_constituency(year, constituency_no)
    payload = last_pages_payload(pdf_path, pages_from_end=3)
    words, lines = choose_summary_page(payload, len(candidates))
    pypdf_payload = last_pages_pypdf_lines(pdf_path, pages_from_end=3)
    pypdf_lines = choose_header_lines_pypdf(pypdf_payload, len(candidates), candidates)
    ordered_candidates = resolve_ordered_candidates(words, lines, pypdf_lines, candidates)
    candidate_votes, valid_votes, electors = extract_summary_values(lines, len(candidates))

    records = []
    for candidate_meta, official_votes in zip(ordered_candidates, candidate_votes):
        row = candidate_meta.row
        record = {
            "year": row.year,
            "assembly_no": row.assembly_no,
            "constituency_no": row.constituency_no,
            "constituency": row.constituency,
            "constituency_type": row.constituency_type,
            "district": row.district,
            "state": row.state,
            "sub_region": row.sub_region,
            "candidate": row.candidate,
            "sex": row.sex,
            "age": row.age,
            "candidate_type": row.candidate_type,
            "education": row.education,
            "profession_main": row.profession_main,
            "profession_second": row.profession_second,
            "party": row.party,
            "party_id": row.party_id,
            "party_type": row.party_type,
            "votes": official_votes,
            "valid_votes": valid_votes,
            "electors": electors or row.electors,
            "vote_share": round((official_votes / valid_votes) * 100, 4) if valid_votes else 0.0,
            "voter_turnout": round(((valid_votes / (electors or row.electors)) * 100), 4) if (electors or row.electors) else row.voter_turnout,
            "position": None,
            "won": False,
            "deposit_lost": False,
            "n_candidates": len(ordered_candidates),
            "margin": None,
            "margin_pct": None,
            "enop": row.enop,
            "incumbent": row.incumbent,
            "recontest": row.recontest,
            "turncoat": row.turncoat,
            "no_terms": row.no_terms,
            "same_constituency": row.same_constituency,
            "same_party": row.same_party,
            "last_party": row.last_party,
            "last_constituency": row.last_constituency,
            "last_poll": row.last_poll,
            "contested": row.contested,
            "source_file": pdf_path.name,
            "source_notes": "Official votes/electors extracted from CEO Gujarat Form-20 PDF; candidate-party metadata taken from existing DB row.",
        }
        records.append(record)

    records.sort(key=lambda item: item["votes"], reverse=True)
    for idx, row in enumerate(records, start=1):
        row["position"] = idx
        row["won"] = idx == 1
        row["deposit_lost"] = idx > 1 and row["vote_share"] < (100 / 6)
    if len(records) > 1:
        records[0]["margin"] = records[0]["votes"] - records[1]["votes"]
        records[0]["margin_pct"] = round((records[0]["margin"] / valid_votes) * 100, 4) if valid_votes else 0.0
    return records


def process_year(year: int, limit: int | None = None) -> Path:
    year_dir = RAW_DIR / str(year)
    if not year_dir.exists():
        raise ValueError(f"Year folder not found: {year_dir}")

    pdfs = sorted(year_dir.glob("*.pdf"))
    pdfs = [pdf for pdf in pdfs if "_Dwarka_" not in pdf.name]
    if limit:
        pdfs = pdfs[:limit]
    if not pdfs:
        raise ValueError(f"No PDFs found for year {year} in {year_dir}")

    records: list[dict] = []
    failures: list[tuple[str, str]] = []
    for pdf_path in pdfs:
        try:
            records.extend(extract_one_pdf(year, pdf_path))
        except Exception as exc:
            failures.append((pdf_path.name, str(exc)))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / f"gujarat_assembly_{year}_official_from_form20.csv"
    pd.DataFrame(records).to_csv(output_path, index=False, encoding="utf-8-sig")

    print(f"Year {year}: extracted {len(records):,} candidate rows from {len(pdfs) - len(failures)} PDFs")
    print(f"Output: {output_path}")
    if failures:
        print(f"Failures: {len(failures)}")
        for name, error in failures[:20]:
            print(f"  - {name}: {error}")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract official candidate rows from CEO Gujarat Form-20 PDFs")
    parser.add_argument("--year", type=int, required=True, help="Election year folder to process")
    parser.add_argument("--limit", type=int, default=None, help="Optional PDF limit for test runs")
    args = parser.parse_args()
    process_year(args.year, args.limit)


if __name__ == "__main__":
    main()
