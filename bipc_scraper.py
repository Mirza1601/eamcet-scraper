import asyncio
import aiohttp
import csv
import os
import time
import itertools

# ── CONFIG ────────────────────────────────────────────────────────────────────
URL             = "https://www.results.manabadi.co.in/2025/AP/EAPCET/Namewise/APEAPCETmResults2025.aspx"
ALL_FILE        = "bipc_all_students.csv"
QUALIFIED_FILE  = "bipc_qualified_ranked.csv"
CHECKPOINT_FILE = "bipc_checkpoint.txt"

MAX_CONCURRENT  = 100
SAVE_EVERY      = 500
SAMPLE_MODE     = True
SAMPLE_SIZE     = 2000

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://www.results.manabadi.co.in/2025/AP/EAPCET/Andhra-Pradesh-AP-EAPCET-AGMED-2025-Results-08062025.htm',
}

# ── CONFIRMED COMPONENTS ──────────────────────────────────────────────────────
STREAM_PREFIX = '95'
STREAM_CODES  = ['01', '02', '03', '04', '05']
SEQ_START     = 1
SEQ_END       = 150

ALIVE_CENTERS = [
    # Band 1: 1152-1196
    1152,1153,1154,1155,1156,1158,1159,1160,1161,1162,1163,1164,1166,1167,
    1169,1170,1172,1173,1174,1175,1177,1178,1179,1180,1181,1182,1183,1185,
    1186,1187,1188,1191,1193,1194,1195,1196,
    # Band 2: 1252-1298
    1252,1253,1254,1255,1256,1257,1258,1260,1263,1264,1265,1266,1267,1269,
    1270,1271,1272,1273,1275,1277,1278,1279,1280,1281,1283,1285,1286,1287,
    1288,1289,1290,1291,1293,1295,1296,1298,
    # Band 3: 1352-1398
    1352,1353,1354,1355,1356,1357,1358,1359,1360,1361,1362,1363,1364,1365,
    1366,1367,1369,1370,1372,1373,1374,1375,1377,1378,1379,1380,1381,1383,
    1385,1386,1387,1388,1390,1391,1393,1394,1395,1396,1398,
    # Band 4: 1452-1498
    1452,1453,1454,1455,1456,1457,1458,1459,1460,1461,1462,1463,1464,1465,
    1466,1467,1469,1470,1471,1472,1473,1474,1475,1478,1479,1480,1481,1482,
    1483,1485,1486,1487,1489,1490,1491,1493,1494,1495,1496,1498
]

# ── CSV FIELDS ────────────────────────────────────────────────────────────────
FIELDS = ['Hall Ticket No', 'Name', 'Score', 'Status', 'Rank']

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
    if '|' not in data_str or 'Referral' in data_str:
        return None
    parts = data_str.strip().split('|')
    if len(parts) < 11:
        return None
    try:
        score_str = parts[8].strip().replace('\u2026', '').replace('...', '')
        rank_str  = parts[9].strip()
        return {
            'Hall Ticket No': parts[0].strip(),
            'Name':           parts[1].strip(),
            'Score':          float(score_str) if score_str else None,
            'Status':         parts[10].strip(),
            'Rank':           int(rank_str) if rank_str.isdigit() else None
        }
    except (ValueError, IndexError):
        return None

# ── ASYNC SCRAPER ─────────────────────────────────────────────────────────────
async def scrape_one(session, semaphore, htno):
    async with semaphore:
        try:
            async with session.get(
                URL,
                params={'htno': htno},
                headers=HEADERS,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                text = await resp.text()
                return htno, parse_response(text.strip())
        except Exception:
            return htno, None

# ── BUILD TICKET LISTS ────────────────────────────────────────────────────────
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

# ── MAIN ASYNC PIPELINE ───────────────────────────────────────────────────────
async def run_async_scraper(tickets_to_run, total_full):
    init_csv(ALL_FILE)

    semaphore   = asyncio.Semaphore(MAX_CONCURRENT)
    buffer      = []
    all_records = []
    lock        = asyncio.Lock()
    found       = 0
    processed   = 0
    start_wall  = time.time()

    connector = aiohttp.TCPConnector(limit=MAX_CONCURRENT)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [
            scrape_one(session, semaphore, ht)
            for ht in tickets_to_run
        ]

        for coro in asyncio.as_completed(tasks):
            htno, record = await coro
            processed += 1

            if record:
                async with lock:
                    buffer.append(record)
                    all_records.append(record)
                    found += 1

                    if len(buffer) >= SAVE_EVERY:
                        flush_to_csv(ALL_FILE, buffer)
                        if not SAMPLE_MODE:
                            save_checkpoint(processed)
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

    qualified = [r for r in all_records if 'disqualified' not in r['Status'].lower()]
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

# ── ENTRY POINT ───────────────────────────────────────────────────────────────
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

    return tickets_to_run, total_full

if __name__ == "__main__":
    tickets_to_run, total_full = run_scraper()
    asyncio.run(run_async_scraper(tickets_to_run, total_full))
