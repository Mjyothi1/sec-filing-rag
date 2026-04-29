#!/usr/bin/env python
"""
scripts/download_from_kaggle_csv.py

Downloads SEC filings using the BUNDLED Kaggle dataset metadata
(`data/kaggle/sec_filings.csv` — from
https://www.kaggle.com/datasets/kharanshuvalangar/sec-filings).

The CSV is shipped with the repo so users don't need a Kaggle account —
just run this script and it pulls a small subset of real SEC filings
directly from sec.gov using the URLs in the dataset.

Note: the dataset is exhibit-heavy. By default we prefer primary
filings (10-Q full reports, 8-K announcements, S-1 prospectuses).
Use --include-exhibits to also pull exhibit documents.

Usage:
    # Default: download 10 primary filings
    python scripts/download_from_kaggle_csv.py

    # Get more
    python scripts/download_from_kaggle_csv.py --count 25

    # Only 10-Q filings
    python scripts/download_from_kaggle_csv.py --form-type 10-Q

    # Specific tickers
    python scripts/download_from_kaggle_csv.py --tickers AAPL MSFT

    # Include exhibits (compensation plans, agreements, etc.)
    python scripts/download_from_kaggle_csv.py --include-exhibits
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

import pandas as pd
import requests

# Make `app.*` importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402


# SEC EDGAR requires a User-Agent on all programmatic requests
# (per https://www.sec.gov/os/accessing-edgar-data)
SEC_USER_AGENT = "SEC-RAG-Hackathon/1.0 (mohan.jyothi@example.com)"
SEC_HEADERS = {
    "User-Agent": SEC_USER_AGENT,
    "Accept-Encoding": "gzip, deflate",
    "Host": "www.sec.gov",
}

DEFAULT_CSV = Path(__file__).resolve().parent.parent / "data" / "kaggle" / "sec_filings.csv"


def safe_filename(company: str, form_type: str, filed_at: str, accession: str, url: str) -> str:
    """Build a safe filename from filing metadata."""
    company = str(company) if pd.notna(company) else "UNKNOWN"
    form_type = str(form_type) if pd.notna(form_type) else "UNK"
    filed_at = str(filed_at) if pd.notna(filed_at) else "0000-00-00"
    accession = str(accession) if pd.notna(accession) else "000000"
    url = str(url) if pd.notna(url) else ""

    # Try to grab the ticker from "COMPANY NAME (TICKER) (CIK ...)" pattern
    ticker = "UNK"
    match = re.search(r"\(([A-Z]{1,5})\)", company)
    if match:
        ticker = match.group(1)

    year = filed_at[:4] if len(filed_at) >= 4 else "0000"
    safe_form = form_type.replace("/", "-")
    accession_short = accession.replace("-", "")[-6:]

    # Preserve the original file extension (.htm, .pdf, .txt)
    ext = ".htm"
    url_lower = url.lower()
    if url_lower.endswith(".pdf"):
        ext = ".pdf"
    elif url_lower.endswith(".txt"):
        ext = ".txt"

    return f"{ticker}_{safe_form}_{year}_{accession_short}{ext}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download SEC filings using the bundled Kaggle dataset metadata."
    )
    parser.add_argument(
        "--csv",
        default=str(DEFAULT_CSV),
        help=f"Path to the Kaggle dataset CSV (default: data/kaggle/sec_filings.csv).",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=10,
        help="Number of filings to download (default: 10).",
    )
    parser.add_argument(
        "--form-type",
        default="any",
        help="Form type to filter, e.g. 10-K, 10-Q, 8-K (default: any).",
    )
    parser.add_argument(
        "--tickers",
        nargs="+",
        default=None,
        help="Filter to specific tickers (e.g. AAPL MSFT).",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=None,
        help="Filter to a specific filing year (e.g. 2022).",
    )
    parser.add_argument(
        "--include-exhibits",
        action="store_true",
        help="Also include exhibit filings (EX-* filing types). "
             "By default we prefer primary documents.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(settings.filings_dir),
        help=f"Where to save filings (default: data/sample_filings).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducible sampling (default: 42).",
    )
    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"❌ CSV not found: {csv_path}")
        print(f"   The Kaggle dataset CSV should be at: {DEFAULT_CSV}")
        return 1

    print(f"📋 Reading metadata from {csv_path.name} ...")
    df = pd.read_csv(csv_path)
    print(f"   Total rows in dataset: {len(df):,}")

    # Dedupe by URL FIRST — the Kaggle dataset repeats URLs many times
    df = df.drop_duplicates(subset=["Filing URL"])
    print(f"   Unique filing URLs: {len(df):,}")

    # Form type filter
    if args.form_type != "any":
        df = df[df["Form Type"] == args.form_type]
        print(f"   After form-type filter ({args.form_type}): {len(df):,}")

    # Prefer primary documents over exhibits (unless user asks for exhibits)
    if not args.include_exhibits:
        df_primary = df[~df["Filing Type"].astype(str).str.startswith("EX-")]
        if len(df_primary) > 0:
            df = df_primary
            print(f"   After excluding exhibits: {len(df):,}")
        else:
            print(f"   ℹ️  No primary documents for this filter — including exhibits.")

    # Ticker filter
    if args.tickers:
        tickers_upper = [t.upper() for t in args.tickers]
        df = df[df["Ticker"].astype(str).str.upper().isin(tickers_upper)]
        print(f"   After ticker filter ({', '.join(tickers_upper)}): {len(df):,}")

    # Year filter
    if args.year:
        df = df[df["Filed At"].astype(str).str.startswith(str(args.year))]
        print(f"   After year filter ({args.year}): {len(df):,}")

    if df.empty:
        print("\n❌ No filings match these filters.")
        print("   Tips:")
        print("   • Try --form-type any  to widen the search")
        print("   • Try --include-exhibits  to allow EX-* documents")
        print("   • Drop --tickers / --year filters")
        return 1

    sample_size = min(args.count, len(df))
    df_sample = df.sample(sample_size, random_state=args.seed)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n📥 Downloading {len(df_sample)} filings to {output_dir} ...")
    print("   (SEC rate-limits to 10 req/sec — adding a polite delay.)\n")

    successes = 0
    failures = 0

    for i, row in enumerate(df_sample.itertuples(index=False), 1):
        # Use getattr by index since column names contain spaces
        company = getattr(row, "_2", None)  # "Company Name"
        ticker = getattr(row, "Ticker", "UNK")
        form_type = getattr(row, "_5", "UNK")  # "Form Type"
        filing_url = getattr(row, "_7", None)  # "Filing URL"
        filed_at = getattr(row, "_8", "")  # "Filed At"
        accession = getattr(row, "_0", "")  # "Accession No"

        if not filing_url or pd.isna(filing_url):
            continue

        ticker_str = str(ticker) if pd.notna(ticker) else "UNK"
        out_name = safe_filename(company, form_type, filed_at, accession, filing_url)
        out_path = output_dir / out_name

        if out_path.exists():
            print(f"  [{i}/{len(df_sample)}] ⏭️  {out_name} (already exists, skipping)")
            successes += 1
            continue

        print(f"  [{i}/{len(df_sample)}] ⬇️  {ticker_str} {form_type} {str(filed_at)[:10]}")
        print(f"            {filing_url}")

        try:
            time.sleep(0.15)  # Be polite to SEC (10 req/sec limit)
            resp = requests.get(filing_url, headers=SEC_HEADERS, timeout=30)
            resp.raise_for_status()

            if len(resp.content) < 500:
                print(f"            ⚠️  Response too small ({len(resp.content)} bytes), skipping")
                failures += 1
                continue

            out_path.write_bytes(resp.content)
            size_kb = len(resp.content) / 1024
            print(f"            ✅ Saved {out_path.name} ({size_kb:,.1f} KB)")
            successes += 1
        except requests.HTTPError as e:
            print(f"            ❌ HTTP error: {e.response.status_code}")
            failures += 1
        except Exception as exc:  # noqa: BLE001
            print(f"            ❌ Failed: {exc}")
            failures += 1

    print(f"\n🎉 Done! Downloaded {successes}/{len(df_sample)} filings ({failures} failed).")

    if successes > 0:
        print(f"\nNext step: build the vector index with these real filings:")
        print(f"    python scripts/ingest.py")
        print(f"\nThen ask questions:")
        print(f"    python -m app.cli ask \"What does this filing discuss?\"")

    return 0 if successes > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
