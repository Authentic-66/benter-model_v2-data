import sqlite3
conn = sqlite3.connect('scripts/racing_full.db')
cur = conn.cursor()

# ITM rate by (odds rank × odds bucket)
print("=" * 90)
print("CT 2022-2026: ITM RATE by tote rank × final odds bucket")
print("=" * 90)

cur.execute("""
    WITH ranked AS (
        SELECT 
            e.race_id, e.finish_pos, e.final_odds,
            RANK() OVER (PARTITION BY e.race_id ORDER BY e.final_odds) AS odds_rank
        FROM entries e
        JOIN races r ON e.race_id = r.id
        JOIN race_days rd ON r.race_day_id = rd.id
        JOIN tracks t ON rd.track_id = t.id
        WHERE t.code = 'CT' AND e.final_odds IS NOT NULL
          AND r.field_size >= 4
          AND rd.race_date BETWEEN '2022-01-01' AND '2026-12-31'
    )
    SELECT 
        odds_rank,
        CASE 
            WHEN final_odds < 2 THEN '01. <2/1'
            WHEN final_odds < 3 THEN '02. 2-3/1'
            WHEN final_odds < 4 THEN '03. 3-4/1'
            WHEN final_odds < 6 THEN '04. 4-6/1'
            WHEN final_odds < 8 THEN '05. 6-8/1'
            WHEN final_odds < 10 THEN '06. 8-10/1'
            WHEN final_odds < 15 THEN '07. 10-15/1'
            WHEN final_odds < 20 THEN '08. 15-20/1'
            ELSE '09. 20/1+'
        END AS odds_bucket,
        COUNT(*) AS n,
        SUM(CASE WHEN finish_pos <= 3 THEN 1 ELSE 0 END) AS itm,
        SUM(CASE WHEN finish_pos = 1 THEN 1 ELSE 0 END) AS wins
    FROM ranked
    WHERE odds_rank <= 6
    GROUP BY odds_rank, odds_bucket
    ORDER BY odds_rank, odds_bucket
""")

results = {}
for rank, bucket, n, itm, wins in cur.fetchall():
    results.setdefault(rank, {})[bucket] = (n, itm, wins)

buckets = ['01. <2/1', '02. 2-3/1', '03. 3-4/1', '04. 4-6/1', 
           '05. 6-8/1', '06. 8-10/1', '07. 10-15/1', '08. 15-20/1', '09. 20/1+']

# Print header
print(f"\n{'Rank':<8}", end='')
for b in buckets:
    print(f"{b:>10}", end='')
print()
print("-" * 90)

# ITM % table
print("\nITM % (n horses in parens):")
for rank in range(1, 7):
    print(f"Rank {rank}: ", end='')
    for b in buckets:
        entry = results.get(rank, {}).get(b)
        if entry and entry[0] >= 20:  # only show if enough samples
            n, itm, wins = entry
            itm_pct = 100 * itm / n
            print(f"  {itm_pct:>4.0f}% ({n:>3})", end='')
        else:
            print(f"          -", end='')
    print()

# Win % table
print("\nWin % (n horses in parens):")
for rank in range(1, 7):
    print(f"Rank {rank}: ", end='')
    for b in buckets:
        entry = results.get(rank, {}).get(b)
        if entry and entry[0] >= 20:
            n, itm, wins = entry
            win_pct = 100 * wins / n
            print(f"  {win_pct:>4.0f}% ({n:>3})", end='')
        else:
            print(f"          -", end='')
    print()

# ROI simulation
print("\nFlat $2 WIN ROI %:")
for rank in range(1, 7):
    print(f"Rank {rank}: ", end='')
    for b in buckets:
        entry = results.get(rank, {}).get(b)
        if entry and entry[0] >= 20:
            n, itm, wins = entry
            # Approximate avg odds for the bucket
            avg_odds_map = {'01. <2/1': 1.4, '02. 2-3/1': 2.5, '03. 3-4/1': 3.5,
                            '04. 4-6/1': 5.0, '05. 6-8/1': 7.0, '06. 8-10/1': 9.0,
                            '07. 10-15/1': 12.5, '08. 15-20/1': 17.5, '09. 20/1+': 30.0}
            avg_odds = avg_odds_map.get(b, 5.0)
            spent = n * 2
            returned = wins * 2 * (avg_odds + 1)  # $2 stake returns $2*(odds+1)
            roi = 100 * (returned - spent) / spent
            print(f"  {roi:>4.0f}%      ", end='')
        else:
            print(f"          -", end='')
    print()

conn.close()