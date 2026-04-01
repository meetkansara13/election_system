from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path


def module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def extract_with_pypdf(pdf_path: Path, page_indices: list[int]) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    parts = []
    for index in page_indices:
        if 0 <= index < len(reader.pages):
            page = reader.pages[index]
            parts.append(f"\n[Page {index + 1}]\n")
            parts.append(page.extract_text() or "")
    return "\n".join(parts)


def extract_with_pypdf2(pdf_path: Path, page_indices: list[int]) -> str:
    from PyPDF2 import PdfReader

    reader = PdfReader(str(pdf_path))
    parts = []
    for index in page_indices:
        if 0 <= index < len(reader.pages):
            page = reader.pages[index]
            parts.append(f"\n[Page {index + 1}]\n")
            parts.append(page.extract_text() or "")
    return "\n".join(parts)


def extract_with_pdfplumber(pdf_path: Path, page_indices: list[int]) -> str:
    import pdfplumber

    parts = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for index in page_indices:
            if 0 <= index < len(pdf.pages):
                page = pdf.pages[index]
                parts.append(f"\n[Page {index + 1}]\n")
                parts.append(page.extract_text() or "")
    return "\n".join(parts)


def page_selection(total_pages: int, max_pages: int, from_end: bool) -> list[int]:
    if from_end:
        start = max(total_pages - max_pages, 0)
        return list(range(start, total_pages))
    return list(range(min(max_pages, total_pages)))


def pdf_page_count(pdf_path: Path) -> int:
    if module_available("pypdf"):
        from pypdf import PdfReader
        return len(PdfReader(str(pdf_path)).pages)
    if module_available("PyPDF2"):
        from PyPDF2 import PdfReader
        return len(PdfReader(str(pdf_path)).pages)
    if module_available("pdfplumber"):
        import pdfplumber
        with pdfplumber.open(str(pdf_path)) as pdf:
            return len(pdf.pages)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect text extractability of a Form-20 PDF")
    parser.add_argument("pdf", help="Path to PDF")
    parser.add_argument("--max-pages", type=int, default=2, help="How many pages to inspect")
    parser.add_argument("--from-end", action="store_true", help="Inspect pages from the end of the PDF")
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        raise SystemExit(f"PDF not found: {pdf_path}")

    print("Available modules:")
    for name in ["pypdf", "PyPDF2", "pdfplumber", "camelot", "tabula", "fitz"]:
        print(f"  {name}: {module_available(name)}")

    extractors = []
    if module_available("pypdf"):
        extractors.append(("pypdf", extract_with_pypdf))
    if module_available("PyPDF2"):
        extractors.append(("PyPDF2", extract_with_pypdf2))
    if module_available("pdfplumber"):
        extractors.append(("pdfplumber", extract_with_pdfplumber))

    if not extractors:
        print("\nNo PDF text extraction libraries available.")
        return

    total_pages = pdf_page_count(pdf_path)
    print(f"\nTotal pages: {total_pages}")
    indices = page_selection(total_pages, args.max_pages, args.from_end)
    print(f"Inspecting pages: {[index + 1 for index in indices]}")

    for label, func in extractors:
        print(f"\n--- Extractor: {label} ---")
        try:
            text = func(pdf_path, indices)
            preview = text[:6000] if text else ""
            print(preview if preview.strip() else "[No text extracted]")
        except Exception as exc:
            print(f"[Failed] {exc}")


if __name__ == "__main__":
    main()
