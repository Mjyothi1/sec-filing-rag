#!/usr/bin/env python
"""
scripts/download_filings.py — fetch a small sample of SEC filings from EDGAR.

EDGAR is free and rate-limited at 10 requests/second. We add a User-Agent
header (required by the SEC) and a polite delay between requests.

Usage:
    python scripts/download_filings.py
    python scripts/download_filings.py --tickers AAPL MSFT GOOGL
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import requests

# Make `app.*` importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402


SEC_USER_AGENT = "SEC-RAG-Hackathon/1.0 (mohan.jyothi@example.com)"
SEC_HEADERS = {"User-Agent": SEC_USER_AGENT, "Accept-Encoding": "gzip, deflate"}

# Map of ticker -> CIK (zero-padded to 10 digits)
TICKER_CIK = {
    "AAPL": "0000320193",
    "MSFT": "0000789019",
    "GOOGL": "0001652044",
    "AMZN": "0001018724",
    "TSLA": "0001318605",
    "META": "0001326801",
    "NVDA": "0001045810",
}


def fetch_recent_10k(ticker: str, output_dir: Path) -> bool:
    """Download the most recent 10-K filing's primary document for a ticker."""
    cik = TICKER_CIK.get(ticker.upper())
    if not cik:
        print(f"  ❌ Unknown ticker: {ticker}")
        return False

    submissions_url = f"https://data.sec.gov/submissions/CIK{cik}.json"
    print(f"  → Fetching submissions index for {ticker} (CIK {cik})")
    resp = requests.get(submissions_url, headers=SEC_HEADERS, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accessions = recent.get("accessionNumber", [])
    primary_docs = recent.get("primaryDocument", [])
    dates = recent.get("filingDate", [])

    # Find first 10-K
    for i, form in enumerate(forms):
        if form == "10-K":
            accession = accessions[i].replace("-", "")
            primary = primary_docs[i]
            filing_date = dates[i]
            year = filing_date.split("-")[0]

            doc_url = (
                f"https://www.sec.gov/Archives/edgar/data/"
                f"{int(cik)}/{accession}/{primary}"
            )
            out_path = output_dir / f"{ticker}_10K_{year}.html"

            print(f"  → Downloading {doc_url}")
            time.sleep(0.2)  # Be polite to SEC.
            doc = requests.get(doc_url, headers=SEC_HEADERS, timeout=60)
            doc.raise_for_status()
            out_path.write_bytes(doc.content)
            print(f"  ✅ Saved {out_path} ({len(doc.content):,} bytes)")
            return True

    print(f"  ❌ No 10-K found for {ticker}")
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Download sample SEC filings.")
    parser.add_argument(
        "--tickers",
        nargs="+",
        default=["AAPL", "MSFT", "GOOGL"],
        help="Tickers to download (default: AAPL MSFT GOOGL).",
    )
    parser.add_argument(
        "--output-dir",
        default=str(settings.filings_dir),
        help="Where to save the downloaded filings.",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Downloading 10-Ks for: {', '.join(args.tickers)}")
    print(f"Output directory: {output_dir}\n")

    success = 0
    for ticker in args.tickers:
        if fetch_recent_10k(ticker, output_dir):
            success += 1
        time.sleep(0.5)  # rate-limit between companies

    print(f"\nDone. {success}/{len(args.tickers)} filings downloaded.")
    return 0 if success > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
