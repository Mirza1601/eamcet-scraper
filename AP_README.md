# AP EAPCET 2025 Results Scraper

A concurrent web scraper that collects student results from the Andhra Pradesh EAPCET 2025 results portal, identifies qualified students, and outputs structured CSV data sorted by rank.

---

## What This Does

- Scrapes Engineering stream student results from `manabadi.co.in`
- Collects: Hall Ticket No, Name, Score, Qualification Status, Rank
- Outputs two CSV files:
  - `ap_all_students.csv` — every student found (qualified and not qualified)
  - `ap_qualified_ranked.csv` — only qualified students, sorted by rank ascending
- Prints a summary with top 10 ranked students on completion
- Supports resuming from checkpoints if the run is interrupted

---

## Hall Ticket Pattern

```
Format: SS + CCCC + XX + NNNN
Example: 550470010103

SS   = Stream prefix (55 = Engineering)
CCCC = 4-digit center code
XX   = 2-digit stream code (01–07)
NNNN = 4-digit sequential number
```

### Confirmed Components

| Component | Values | Notes |
|-----------|--------|-------|
| Stream Prefix | `55` | Engineering only |
| Center Codes | 437 confirmed codes (152–1098) | Verified via diagnostic scraping |
| Stream Codes | `01` through `07` | Varies per center |
| Sequential Range | `0001` to `0150` | Confirmed ceiling per diagnostic |

> Center codes follow a banded pattern (e.g. 152–197, 252–297, 352–398...) and were confirmed by probing all codes from 100–1200. Do not modify without re-running diagnostics.

---

## Key Difference from TS EAMCET

Unlike the TS scraper, **AP EAPCET requires browser-like headers** on every request. The server returns a `Referral Denied` error without them. These headers are already built into the scraper — no action needed.

---

## How to Run

### Option 1: Run Locally

```bash
# Install dependency
pip install requests

# Test on a small sample first (SAMPLE_MODE = True by default)
python ap_scraper.py

# When sample looks good, open ap_scraper.py and set:
# SAMPLE_MODE = False
# Then run again for full scrape
python ap_scraper.py
```

### Option 2: Run on GitHub Actions (Recommended — No PC Required)

See the [GitHub Actions Guide](#github-actions-guide) section below.

---

## Output Files

### `ap_all_students.csv`
Contains every student record found during the scrape.

| Column | Description |
|--------|-------------|
| Hall Ticket No | Student's hall ticket number |
| Name | Student's full name |
| Score | Total EAPCET score |
| Status | Qualified or Not Qualified |
| Rank | Rank (empty if not qualified) |

### `ap_qualified_ranked.csv`
Contains only Qualified students, sorted by Rank ascending (Rank 1 at top).
Same columns as above.

---

## Configuration

Open `ap_scraper.py` and modify these values at the top:

| Variable | Default | Description |
|----------|---------|-------------|
| `SAMPLE_MODE` | `True` | Set to `False` for full scrape |
| `SAMPLE_SIZE` | `2000` | Tickets to test in sample mode |
| `MAX_WORKERS` | `50` | Concurrent threads |
| `SAVE_EVERY` | `500` | Save to CSV every N records found |

---

## Checkpointing

If the scraper is interrupted during a full run, it saves progress to `ap_checkpoint.txt`. Re-run the script and it resumes from where it left off.

To start fresh, delete `ap_checkpoint.txt`, `ap_all_students.csv`, and `ap_qualified_ranked.csv`.

---

## GitHub Actions Guide

### First-Time Setup

If you haven't already set up the repo, follow the setup steps in the main [TS EAMCET README](README.md) first — the repo setup and permissions are the same.

### Running the AP Scraper

1. Go to your GitHub repository
2. Click the **Actions** tab
3. Click **AP EAPCET Scraper** in the left sidebar
4. Click **Run workflow** → **Run workflow**
5. Close your browser or turn off your PC — it keeps running on GitHub's servers

**Estimated runtime: ~2.6 hours**

When finished, `ap_all_students.csv` and `ap_qualified_ranked.csv` will be automatically committed to your repo. Go to the repo main page and download them.

### Monitoring Progress

1. Click the **Actions** tab
2. Click the running workflow (yellow spinning circle)
3. Click the **scrape** job
4. Watch live logs showing speed and records found

---

## Scaling to Other Streams / States

This scraper currently covers **AP EAPCET Engineering (stream prefix 55)** only.

To add Agriculture or Pharmacy streams:
1. Find a real hall ticket for that stream
2. Identify the stream prefix (the first two digits)
3. Run the center code diagnostic to find alive centers for that stream
4. Update `STREAM_PREFIX` and `ALIVE_CENTERS` in the config

For Telangana EAMCET, see the separate [TS EAMCET scraper](README.md).

---

## Project Structure

```
eamcet-scraper/
├── scraper.py                        # TS EAMCET scraper
├── ap_scraper.py                     # AP EAPCET scraper (this file)
├── requirements.txt                  # Python dependencies
├── README.md                         # TS EAMCET documentation
├── AP_README.md                      # AP EAPCET documentation (this file)
├── .github/
│   └── workflows/
│       ├── scrape.yml                # GitHub Actions — TS EAMCET
│       └── scrape_ap.yml             # GitHub Actions — AP EAPCET
├── all_students.csv                  # TS output (generated on run)
├── qualified_ranked.csv              # TS qualified output (generated on run)
├── ap_all_students.csv               # AP output (generated on run)
├── ap_qualified_ranked.csv           # AP qualified output (generated on run)
└── checkpoint.txt / ap_checkpoint.txt  # Resume files (generated on run)
```

---

## Important Notes

- This scraper accesses publicly available exam results
- Built with responsible scraping practices — 50 concurrent workers with timeouts
- Do not increase `MAX_WORKERS` beyond 100
- The portal being scraped is `results.manabadi.co.in` — a public government results website
- AP EAPCET status field uses `Qualified` / `Not Qualified` (mixed case) — handled automatically
