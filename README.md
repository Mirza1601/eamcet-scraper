
# TS EAMCET 2025 Results Scraper

A concurrent web scraper that collects student results from the Telangana EAMCET 2025 results portal, identifies qualified students, and outputs structured CSV data sorted by rank.

---

## What This Does

- Scrapes student results from `manabadi.co.in` using confirmed hall ticket number patterns
- Collects: Hall Ticket No, Name, Score, Qualification Status, Rank
- Outputs two CSV files:
  - `all_students.csv` — every student found (qualified and not qualified)
  - `qualified_ranked.csv` — only qualified students, sorted by rank ascending
- Prints a summary with top 10 ranked students on completion
- Supports resuming from checkpoints if the run is interrupted

---

## Hall Ticket Pattern

```
Format: YY + CC + Letter + NNNNN
Example: 2521A10001

YY     = Year prefix (25 for 2025)
CC     = Two-digit center code (21–26)
Letter = Stream/center letter code
NNNNN = Sequential number (5 digits, zero-padded)
```

### Confirmed Letter Code Ranges

| Letter | Sequential Range | Notes |
|--------|-----------------|-------|
| A, C, D, E, L | 1002 – 19109 | Wide range |
| S | 1002 – 9999 | Narrow range |
| H | 1002 – 6999 | Narrow range |
| G, R | 1002 – 4999 | Narrow range |
| K | 1002 – 2999 | Narrow range |
| N | 1002 – 3999 | Non-contiguous gaps |

> These ranges were confirmed through diagnostic scraping. Modifying them without re-running diagnostics may result in missed students or wasted requests.

---

## How to Run

### Option 1: Run Locally

```bash
# Install dependency
pip install requests

# Test on a small sample first (SAMPLE_MODE = True by default)
python scraper.py

# When sample looks good, open scraper.py and set:
# SAMPLE_MODE = False
# Then run again for full scrape
python scraper.py
```

### Option 2: Run on GitHub Actions (Recommended — No PC Required)

See the [GitHub Actions Guide](#github-actions-guide) section below.

---

## Output Files

### `all_students.csv`
Contains every student record found during the scrape.

| Column | Description |
|--------|-------------|
| Hall Ticket No | Student's hall ticket number |
| Name | Student's full name |
| Score | Total EAMCET score |
| Status | QUALIFIED or NOT QUALIFIED |
| Rank | Rank (empty if not qualified) |

### `qualified_ranked.csv`
Contains only QUALIFIED students, sorted by Rank ascending (Rank 1 at top).
Same columns as above.

---

## Configuration

Open `scraper.py` and modify these values at the top:

| Variable | Default | Description |
|----------|---------|-------------|
| `SAMPLE_MODE` | `True` | Set to `False` for full scrape |
| `SAMPLE_SIZE` | `2000` | Tickets to test in sample mode |
| `MAX_WORKERS` | `50` | Concurrent threads (increase for speed, decrease if getting blocked) |
| `SAVE_EVERY` | `500` | Save to CSV every N records found |

---

## Checkpointing

If the scraper is interrupted during a full run, it saves its progress to `checkpoint.txt`. Simply re-run the script and it will resume from where it left off without re-scraping completed tickets.

To start fresh, delete `checkpoint.txt`, `all_students.csv`, and `qualified_ranked.csv`.

---

## GitHub Actions Guide

This is the recommended way to run the scraper without keeping your PC on.

### First-Time Setup

**Step 1: Create a GitHub repository**
1. Go to [github.com](https://github.com) and sign in
2. Click the `+` button → `New repository`
3. Name it `eamcet-scraper`
4. Set it to **Private**
5. Click `Create repository`

**Step 2: Push this code to GitHub**

```bash
# In your terminal, navigate to the project folder
cd eamcet_scraper

# Initialize git
git init
git add .
git commit -m "Initial commit — EAMCET scraper"

# Connect to your GitHub repo (replace YOUR_USERNAME)
git remote add origin https://github.com/YOUR_USERNAME/eamcet-scraper.git
git branch -M main
git push -u origin main
```

**Step 3: Enable GitHub Actions write permissions**
1. In your GitHub repo, go to `Settings`
2. Click `Actions` → `General` in the left sidebar
3. Scroll to `Workflow permissions`
4. Select `Read and write permissions`
5. Click `Save`

### Running the Scraper

**Step 1:** Go to your GitHub repository

**Step 2:** Click the `Actions` tab at the top

**Step 3:** Click `EAMCET Scraper` in the left sidebar

**Step 4:** Click `Run workflow` → `Run workflow`

**Step 5:** The scraper will start running on GitHub's servers. You can close your browser or turn off your PC — it will keep running.

**Step 6:** When finished (estimated 3–6 hours), the CSV files will be automatically committed back to your repository. Go to your repo's main page and download `all_students.csv` and `qualified_ranked.csv`.

### Monitoring Progress

While the workflow is running:
1. Click the `Actions` tab
2. Click the running workflow
3. Click the `scrape` job
4. You can watch live logs showing speed and records found

---

## Scaling to Other States / Exams

This scraper is built to be reusable. To scrape AP EAMCET or BIPC data:

1. Run the diagnostic scripts to identify the new hall ticket pattern components
2. Update `YEAR`, `TWO_DIGIT_CODES`, and `LETTER_RANGES` in `scraper.py`
3. Update the `BASE_URL` if the results portal is different
4. Run in sample mode first to validate before full scrape

For running multiple states simultaneously, use separate GitHub repos or separate branches — each with their own config — and trigger the workflows in parallel.

---

## Project Structure

```
eamcet_scraper/
├── scraper.py                        # Main scraper script
├── requirements.txt                  # Python dependencies
├── README.md                         # This file
├── .github/
│   └── workflows/
│       └── scrape.yml                # GitHub Actions workflow
├── all_students.csv                  # Output: all students (generated on run)
├── qualified_ranked.csv              # Output: qualified only, sorted by rank (generated on run)
└── checkpoint.txt                    # Resume file (generated on run)
```

---

## Important Notes

- This scraper accesses publicly available exam results
- Built with responsible scraping practices — 50 concurrent workers with timeouts
- Do not increase `MAX_WORKERS` beyond 100 as it may cause connection issues
- The portal being scraped is `results.manabadi.co.in` — a public government results website
=======
# eamcet-scraper
TS EAMCET 2025 Results Scrape
>>>>>>> 76f9167984038a3acee58f501a41a70fb11d2e3f
