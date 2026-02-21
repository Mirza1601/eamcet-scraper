import requests
import time
import csv
import os
import itertools
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

BASE_URL        = "https://www.results.manabadi.co.in/2025/AP/EAPCET/Namewise/APEAPCETResults2025.aspx"
ALL_FILE        = "ap_all_students.csv"
QUALIFIED_FILE  = "ap_qualified_ranked.csv"
CHECKPOINT_FILE = "ap_checkpoint.txt"
MAX_WORKERS     = 50
SAVE_EVERY      = 500
SAMPLE_MODE     = True
SAMPLE_SIZE     = 2000

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://www.results.manabadi.co.in/2025/AP/EAPCET/Namewise/Andhra-Pradesh-AP-EAPCET-Results-2025-ENGG-08062025.htm',
}

STREAM_PREFIX = '55'
STREAM_CODES  = ['01','02','03','04','05','06','07']
SEQ_START     = 1
SEQ_END       = 150

ALIVE_CENTERS = [
    152,153,154,155,156,157,158,159,160,161,163,164,165,166,167,169,170,171,
    172,173,174,175,176,177,178,179,180,181,182,183,184,185,186,187,188,189,
    190,191,192,193,194,195,196,197,252,253,254,255,256,257,258,259,260,261,
    262,264,265,266,267,268,269,270,271,272,273,274,275,276,277,278,279,280,
    281,282,283,284,285,286,287,288,289,290,291,292,293,294,295,296,297,352,
    354,355,356,357,358,359,363,364,365,366,367,368,369,370,371,372,373,374,
    376,377,379,380,381,382,383,384,385,386,387,388,389,390,391,392,393,394,
    395,396,398,452,453,454,455,456,457,458,459,460,461,462,463,464,465,466,
    467,468,469,470,471,472,473,474,475,476,477,479,480,481,482,483,484,486,
    487,488,489,490,491,493,494,495,496,552,553,554,555,556,557,558,559,560,
    561,562,563,564,565,566,567,568,569,570,571,572,573,574,575,576,577,579,
    580,582,583,584,585,587,588,589,590,591,592,593,594,595,596,597,652,653,
    654,655,656,657,659,660,661,662,663,664,665,666,667,668,669,670,671,672,
    673,674,675,676,677,679,680,681,682,683,684,685,686,687,688,689,690,691,
    692,693,694,695,696,697,752,753,754,755,756,757,758,759,760,761,762,763,
    764,765,766,767,768,769,770,771,772,773,774,775,776,777,778,779,780,781,
    782,783,784,785,786,787,788,789,791,792,793,794,795,796,798,852,853,854,
    855,856,857,858,859,860,861,862,863,864,865,866,867,868,869,870,871,872,
    873,874,875,876,877,878,879,880,881,882,883,884,885,886,887,889,890,891,
    893,894,895,896,952,953,954,955,956,957,958,959,960,961,962,963,964,965,
    966,967,968,969,970,971,972,973,974,975,976,977,979,980,981,982,983,984,
    985,986,987,988,989,990,991,992,993,994,995,996,998,1052,1053,1054,1055,
    1056,1057,1058,1059,1060,1061,1062,1063,1064,1065,1066,1067,1068,1069,
    1071,1072,1073,1074,1075,1076,1077,1078,1079,1080,1081,1082,1083,1084,
    1085,1086,1087,1088,1089,1090,1091,1092,1093,1094,1095,1096,1097,1098
]

FIELDS = ['Hall Ticket No', 'Name', 'Score', 'Status', 'Rank']

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

def parse_response(data_str):
    if '|' not in data_str or 'Referral' in data_str:
        return None
    parts = data_str.strip().split('|')
    if len(parts) < 10:
        return None
    try:
        score_str = parts[7].strip().replace('\u2026', '').replace('...', '')
        return {
            'Hall Ticket No': parts[0].strip(),
            'Name':           parts[1].strip(),
            'Score':          float(score_str) if score_str else None,
            'Status':         parts[9].strip(),
            'Rank':           int(parts[8].strip()) if parts[8].strip() not in ['-', ''] else None
        }
    except (ValueError, IndexError):
        return None

def scrape_one(htno):
    try:
        resp = requests.get(BASE_URL, params={'htno': htno}, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        return htno, parse_response(resp.text.strip())
    except Exception:
        return htno, None

def build_full_ticket_list():
    tickets = []
    for center, stream, seq in itertools.product(
        ALIVE_CENTERS, STREAM_CODES, range(SEQ_START, SEQ_END + 1)
    ):
        tickets.append(f"{STREAM_PREFIX}{center:04d}{stream}{seq:04d}")
    return tickets

def build_sample_tickets():
    sample_centers = ALIVE_CENTERS[:30]
    tickets = []
    for center, stream, seq in itertools.product(
        sample_centers, STREAM_CODES, range(SEQ_START, SEQ_END + 1)
    ):
        tickets.append(f"{STREAM_PREFIX}{center:04d}{stream}{seq:04d}")
    return tickets[:SAMPLE_SIZE]

def run_scraper():
    all_tickets = build_full_ticket_list()
    total_full  = len(all_tickets)

    if SAMPLE_MODE:
        tickets_to_run = build_sample_tickets()
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
                            f"  [SAVE] {found} students | "
                            f"{processed:,} processed | "
                            f"{rate:.1f} req/s | "
                            f"ETA: {eta_hrs:.1f} hrs"
                        )
                        buffer.clear()

    if buffer:
        flush_to_csv(ALL_FILE, buffer)
        print(f"  [FINAL FLUSH] {len(buffer)} records written")

    wall_time = time.time() - start_wall

    qualified = [r for r in all_records if r['Status'].lower() == 'qualified']
    qualified_sorted = sorted(
        qualified,
        key=lambda x: x['Rank'] if x['Rank'] is not None else float('inf')
    )

    with open(QUALIFIED_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(qualified_sorted)

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
    print("-" * 75)
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
        print(f"  Set SAMPLE_MODE = False and run again for full scrape")
        full_eta = total_full / (processed / wall_time) / 3600
        print(f"  Estimated full scrape: {full_eta:.1f} hours for {total_full:,} tickets")
        print(f"{'='*65}")

run_scraper()
