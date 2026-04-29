# Kaggle SEC Filings Dataset

This folder contains the **bundled Kaggle dataset** specified in the
hackathon problem statement (F7).

## Source

- **Dataset:** SEC Filings
- **URL:** <https://www.kaggle.com/datasets/kharanshuvalangar/sec-filings>
- **Author:** Kharanshu Valangar
- **License:** As specified on Kaggle (typically CC0 or similar — verify on Kaggle)

## File

- **`sec_filings.csv`** (~2 MB)
  - 10,000 rows of SEC filing metadata
  - Columns: `Accession No`, `CIK`, `Company Name`, `Ticker`, `Description`,
    `Form Type`, `Filing Type`, `Filing URL`, `Filed At`
  - Form types include 10-K, 10-Q, 8-K, S-1, exhibits, and amendments
  - Date range: 2004–2023
  - 103 unique filing URLs (the dataset has many duplicate rows for exhibits
    of the same filing)

## How we use it

The CSV provides **metadata only** — it tells us *where* the actual filings
live on sec.gov. The companion script `scripts/download_from_kaggle_csv.py`
reads this CSV and downloads the full filing content directly from SEC EDGAR.

## Why we bundle it

By shipping the CSV with the repo, users don't need:
- A Kaggle account
- A Kaggle API token
- The `kaggle` CLI installed

They can just clone the repo and run the download script immediately.

## Usage

```bash
# Download 10 random filings from the dataset
python scripts/download_from_kaggle_csv.py

# Filter to specific form types or tickers
python scripts/download_from_kaggle_csv.py --form-type 10-K --count 5
python scripts/download_from_kaggle_csv.py --tickers AAPL MSFT
python scripts/download_from_kaggle_csv.py --year 2022 --include-exhibits
```

Downloaded filings go to `data/sample_filings/` and can then be indexed
with `python scripts/ingest.py`.
