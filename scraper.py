import requests
import time
import csv
import os
import itertools
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

# ── CONFIG ────────────────────────────────────────────────────────────────────
BASE_URL        = "https://www.results.manabadi.co.in/2025/TS/EAMCET/Namewise/TSEAMCETResults2025.aspx"
ALL_FILE        = "all_students.csv"
QUALIFIED_FILE  = "qualified_ranked.csv"
CHECKPOINT_FILE = "checkpoint.txt"

MAX_WORKERS     = 50
SAVE_EVERY      = 500

# ── SAMPLE MODE ───────────────────────────────────────────────────────────────
# Set SAMPLE_MODE = True to test on a small subset first
# Set SAMPLE_MODE = False to run the full scrape
SAMPLE_MODE     = True
SAMPLE_SIZE     = 2000

# ── CONFIRMED HALL TICKET COMPONENTS ─────────────────────────────────────────
# Pattern: YY + CC + Letter + NNNNN
# Confirmed via diagnostic scraping — do not modify without re-running diagnostics

YEAR = '25'
TWO_DIGIT_CODES = ['21', '22', '23', '24', '25', '26']

# Each letter code has its own confirmed sequential range
# Wide-range letters: exist from ~1002 all the way to ~19109
# Narrow-range letters: only exist in lower sequential ranges
LETTER_RANGES = {
    'A': (1002, 19109),
    'C': (1002, 19109),
    'D': (1002, 19109),
    'E': (1002, 19109),
    'L': (1002, 19109),
    'S': (1002, 9999),
    'H': (1002, 6999),
    'G': (1002, 4999),
    'R': (1002, 4999),
    'K': (1002, 2999),
    'N': (1002, 3999),   # Note: non-contiguous gaps observed — hits still captured
}

# ── CSV FIELDS ────────────────────────────────────────────────────────────────
FIELDS = ['Hall Ticket No', 'Name', 'Score', 'Status', 'Rank']

# ── FIELD MAPPING (confirmed from raw response diagnostic) ───────────────────
# Raw pipe-separated response format:
# [0]: internal_id | [1]: hall_ticket | [2]: name | [3]: math | [4]: physics
# [5]: chemistry   | [6]: total_score | [7]: status | [8]: rank | [9]: branch

# ── CHECKPOINT ────────────────────────────────────────────────────────────────
def load_checkpoint():
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, 'r') as f:
            val = f.read().strip()
            if val.isdigit():
                print(f"[RESUME] Resuming from index {val}")
                return int(val)
    return 0

def save_checkpoint(index):
    with open(CHECKPOINT_FILE, 'w') as f:
        f.write(str(index))

# ── CSV HELPERS ───────────────────────────────────────────────────────────────
def init_csv(filepath):
    if not os.path.exists(filepath):
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            csv.DictWriter(f, fieldnames=FIELDS).writeheader()
        print(f"[INIT] Created {filepath}")
    else:
        print(f"[INIT] Appending to existing {filepath}")

def flush_to_csv(filepath, records):
    with open(filepath, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writerows(records)

# ── PARSER ────────────────────────────────────────────────────────────────────
def parse_response(data_str):
    if '|' not in data_str or data_str.strip().lower().startswith('invalid'):
        return None
    parts = data_str.strip().split('|')
    if len(parts) < 9:
        return None
    try:
        return {
            'Hall Ticket No': parts[1].strip(),
            'Name':           parts[2].strip(),
            'Score':          float(parts[6].strip()),
            'Status':         parts[7].strip(),
            'Rank':           int(parts[8].strip()) if parts[8].strip() not in ['-', ''] else None
        }
    except (ValueError, IndexError):
        return None

# ── SCRAPER ───────────────────────────────────────────────────────────────────
def scrape_one(htno):
    try:
        resp = requests.get(BASE_URL, params={'htno': htno}, timeout=10)
        resp.raise_for_status()
        return htno, parse_response(resp.text.strip())
    except Exception:
        return htno, None

# ── BUILD TICKET LIST ─────────────────────────────────────────────────────────
def build_ticket_list():
    """
    Generates all hall ticket numbers using confirmed components and ranges.
    Total keyspace: ~710,000 tickets across all CC codes and letter codes.
    """
    tickets = []
    for cc, (letter, (seq_start, seq_end)) in itertools.product(
        TWO_DIGIT_CODES, LETTER_RANGES.items()
    ):
        for seq in range(seq_start, seq_end + 1):
            tickets.append(f"{YEAR}{cc}{letter}{seq:05d}")
    return tickets

# ── MAIN SCRAPER ──────────────────────────────────────────────────────────────
def run_scraper():
    all_tickets = build_ticket_list()
    total_full  = len(all_tickets)

    if SAMPLE_MODE:
        step = max(1, total_full // SAMPLE_SIZE)
        tickets_to_run = all_tickets[::step][:SAMPLE_SIZE]
        print(f"[SAMPLE MODE] Running {len(tickets_to_run):,} tickets")
        print(f"              from full keyspace of {total_full:,}")
        print(f"              Set SAMPLE_MODE = False for full scrape\n")
    else:
        start_index    = load_checkpoint()
        tickets_to_run = all_tickets[start_index:]
        print(f"[FULL MODE] {len(tickets_to_run):,} tickets remaining of {total_full:,}\n")

    init_csv(ALL_FILE)

    buffer      = []
    all_records = []
    lock        = Lock()
    found       = 0
    processed   = 0
    start_wall  = time.time()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_idx = {
            executor.submit(scrape_one, ht): i
            for i, ht in enumerate(tickets_to_run)
        }

        for future in as_completed(future_to_idx):
            idx          = future_to_idx[future]
            htno, record = future.result()
            processed   += 1

            if record:
                with lock:
                    buffer.append(record)
                    all_records.append(record)
                    found += 1

                    if len(buffer) >= SAVE_EVERY:
                        flush_to_csv(ALL_FILE, buffer)
                        if not SAMPLE_MODE:
                            save_checkpoint(idx)
                        elapsed = time.time() - start_wall
                        rate    = processed / elapsed
                        eta_hrs = (len(tickets_to_run) - processed) / rate / 3600
                        print(
                            f"  [SAVE] {found} students found | "
                            f"{processed:,} processed | "
                            f"{rate:.1f} req/s | "
                            f"ETA: {eta_hrs:.1f} hrs"
                        )
                        buffer.clear()

    # Final flush for remaining buffer
    if buffer:
        flush_to_csv(ALL_FILE, buffer)
        print(f"  [FINAL FLUSH] {len(buffer)} records written")

    wall_time = time.time() - start_wall

    # ── BUILD QUALIFIED CSV ───────────────────────────────────────────────────
    qualified        = [r for r in all_records if r['Status'] == 'QUALIFIED']
    qualified_sorted = sorted(
        qualified,
        key=lambda x: x['Rank'] if x['Rank'] is not None else float('inf')
    )

    with open(QUALIFIED_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(qualified_sorted)

    # ── PRINT SUMMARY ─────────────────────────────────────────────────────────
    print("\n" + "=" * 65)
    print("SCRAPE SUMMARY")
    print("=" * 65)
    print(f"  Total tickets processed : {processed:,}")
    print(f"  Total students found    : {found:,}")
    print(f"  Qualified students      : {len(qualified_sorted):,}")
    print(f"  Not Qualified           : {found - len(qualified_sorted):,}")
    print(f"  Time taken              : {wall_time:.1f}s")
    print(f"  Avg speed               : {processed / wall_time:.1f} req/s")
    print(f"\n  Saved → {ALL_FILE}")
    print(f"  Saved → {QUALIFIED_FILE}")

    print(f"\nTOP 10 QUALIFIED STUDENTS:")
    print(f"{'Rank':<8} {'Hall Ticket':<15} {'Name':<35} {'Score'}")
    print("-" * 70)
    for r in qualified_sorted[:10]:
        print(
            f"  {str(r['Rank']):<6} "
            f"{r['Hall Ticket No']:<15} "
            f"{r['Name']:<35} "
            f"{r['Score']}"
        )

    if SAMPLE_MODE:
        print(f"\n{'='*65}")
        print(f"  SAMPLE COMPLETE — results look good?")
        print(f"  Set SAMPLE_MODE = False in scraper.py and run again")
        print(f"  Estimated full scrape time at current speed:")
        full_eta = total_full / (processed / wall_time) / 3600
        print(f"  → {full_eta:.1f} hours for {total_full:,} tickets")
        print(f"{'='*65}")

# ── ENTRY POINT ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    run_scraper()
