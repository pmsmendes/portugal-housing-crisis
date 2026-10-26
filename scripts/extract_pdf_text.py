"""Extract the text of a PDF report page by page, to check figures transcribed into data/external (e.g. lending_standards.csv).

Usage: uv run python scripts/extract_pdf_text.py <report.pdf> [out.txt]
Prints to stdout when no output file is given. Pages are marked ``=== p<N>`` (the PDF page, not the printed page number).
"""

import sys
from pathlib import Path

from pypdf import PdfReader


def extract(pdf: Path) -> str:
    reader = PdfReader(pdf)
    return "\n".join(
        f"=== p{i}\n{page.extract_text() or ''}" for i, page in enumerate(reader.pages, start=1)
    )


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        sys.exit(__doc__)
    text = extract(Path(sys.argv[1]))
    if len(sys.argv) == 3:
        Path(sys.argv[2]).write_text(text, encoding="utf-8")
    else:
        print(text)
