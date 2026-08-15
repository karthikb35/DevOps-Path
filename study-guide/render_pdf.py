#!/usr/bin/env python3
"""Render a DevOps study-guide HTML book to PDF with headless Chromium (Playwright).

WHY Chromium and not weasyprint/pandoc: the books use @page rules, CSS gradients,
print-color-adjust:exact, SVG diagrams and custom fonts. Chromium's print pipeline
is the only engine that reproduces that layout faithfully — it is exactly what
"Print to PDF" in Chrome uses.

Usage:
    python render_pdf.py <input.html> <output.pdf>
    python render_pdf.py study-guide/book-1-git-github-actions.html out/Book-1-Git-GitHub-Actions.pdf

Local one-time setup:
    pip install playwright
    python -m playwright install chromium

The CI workflow (.github/workflows/docs-pdf.yml) calls this once per book and only
for books whose HTML (or the shared CSS) changed; unchanged books are carried over
from the previous rolling release.
"""

from __future__ import annotations

from pathlib import Path
import sys


def render(html_path: str, pdf_path: str) -> None:
    from playwright.sync_api import sync_playwright

    src = Path(html_path).resolve()
    if not src.is_file():
        raise FileNotFoundError(f"HTML source not found: {src}")

    out = Path(pdf_path).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        # Load from file:// URI so relative <link> to the shared CSS resolves
        # exactly as it does when opened in a browser.
        page.goto(src.as_uri(), wait_until="networkidle")
        page.pdf(
            path=str(out),
            prefer_css_page_size=True,  # honour @page { size: A4 }
            print_background=True,  # keep dark cover gradients and coloured boxes
        )
        browser.close()
    print(f"wrote {pdf_path}")


def render_all(study_guide_dir: str = "study-guide", out_dir: str = "out") -> None:
    """Render every book HTML in the study-guide directory."""
    books = sorted(Path(study_guide_dir).glob("book-*.html"))
    books += sorted(Path(study_guide_dir).glob("The-DevOps-Path.html"))
    for html in books:
        pdf_name = (
            html.stem.replace("book-", "Book-").replace("-", "-").title() + ".pdf"
        )
        render(str(html), str(Path(out_dir) / pdf_name))


def main(argv: list[str]) -> int:
    if len(argv) == 2 and argv[1] == "--all":
        render_all()
        return 0
    if len(argv) != 3:
        print("usage: render_pdf.py <input.html> <output.pdf>", file=sys.stderr)
        print(
            "       render_pdf.py --all                     (render all books)",
            file=sys.stderr,
        )
        return 2
    render(argv[1], argv[2])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
