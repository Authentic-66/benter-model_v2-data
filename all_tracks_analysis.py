import sqlite3
conn = sqlite3.connect('scripts/racing_full.db')
cur = conn.cursor()

TRACKS = ['GP', 'CT', 'MNR']

for track in TRACKS:
    print()
    print("#" * 90)
    print(f"###  {track} 2022-2026 ANALYSIS")
    print("#" * 90)
    
    # Basic favorite stats
    cur.execute("""
        WITH ranked AS (
            SELECT 
                e.race_id, e.finish_pos, e.final_odds,
                RANK() OVER (PARTITION BY e.race_id ORDER BY e.final_odds) AS odds_rank
            FROM entries e
            JOIN races r ON e.race_id = r.id
            JOIN race_days rd ON r.race_day_id = rd.id
            JOIN tracks t ON rd.track_id = t.id
            WHERE t.code = ? AND e.final_odds IS NOT NULL
              AND r.field_size >= 4
              AND rd.race_date BETWEEN '2022-01-01' AND '2026-12-31'
        )
        SELECT 
            COUNT(DISTINCT race_id) AS total_races,
            SUM(CASE WHEN odds_rank=1 AND finish_pos=1 THEN 1 ELSE 0 END) AS won,
            SUM(CASE WHEN odds_rank=1 AND finish_pos=2 THEN 1 ELSE 0 END) AS second,
            SUM(CASE WHEN odds_rank=1 AND finish_pos=3 THEN 1 ELSE 0 END) AS third,
            SUM(CASE WHEN odds_rank=1 AND finish_pos<=3 THEN 1 ELSE 0 END) AS itm,
            AVG(CASE WHEN odds_rank=1 THEN 
                (SELECT field_size FROM races WHERE id=ranked.race_id) 
                ELSE NULL END) as avg_field
        FROM ranked
    """, (track,))
    total, won, second, third, itm, avg_fs = cur.fetchone()
    print(f"\nRaces: {total:,}  |  Avg field size: {avg_fs:.1f}")
    print(f"Fav Won: {won:,} ({100*won/total:.1f}%)  |  Fav 2nd: {second:,} ({100*second/total:.1f}%)  |  Fav 3rd: {third:,} ({100*third/total:.1f}%)  |  Fav ITM: {itm:,} ({100*itm/total:.1f}%)")
    
    # ITM by odds bucket
    print(f"\n--- {track}: ITM rate by odds bucket (all horses) ---")
    cur.execute("""
        SELECT 
            CASE 
                WHEN final_odds < 1 THEN '01. <1/1'
                WHEN final_odds < 2 THEN '02. 1-2/1'
                WHEN final_odds < 3 THEN '03. 2-3/1'
                WHEN final_odds < 4 THEN '04. 3-4/1'
                WHEN final_odds < 6 THEN '05. 4-6/1'
                WHEN final_odds < 8 THEN '06. 6-8/1'
                WHEN final_odds < 10 THEN '07. 8-10/1'
                WHEN final_odds < 15 THEN '08. 10-15/1'
                WHEN final_odds < 20 THEN '09. 15-20/1'
                ELSE '10. 20/1+'
            END AS odds_bucket,
            COUNT(*) AS n,
            SUM(CASE WHEN finish_pos = 1 THEN 1 ELSE 0 END) AS wins,
            SUM(CASE WHEN finish_pos <= 3 THEN 1 ELSE 0 END) AS itm
        FROM entries e
        JOIN races r ON e.race_id = r.id
        JOIN race_days rd ON r.race_day_id = rd.id
        JOIN tracks t ON rd.track_id = t.id
        WHERE t.code = ? AND e.final_odds IS NOT NULL
          AND r.field_size >= 4
          AND rd.race_date BETWEEN '2022-01-01' AND '2026-12-31'
        GROUP BY odds_bucket
        ORDER BY odds_bucket
    """, (track,))
    
    avg_odds_map = {'01. <1/1': 0.7, '02. 1-2/1': 1.5, '03. 2-3/1': 2.5, '04. 3-4/1': 3.5,
                    '05. 4-6/1': 5.0, '06. 6-8/1': 7.0, '07. 8-10/1': 9.0,
                    '08. 10-15/1': 12.5, '09. 15-20/1': 17.5, '10. 20/1+': 30.0}
    
    print(f"{'Bucket':<14}{'Horses':>10}{'Win %':>10}{'ITM %':>10}{'Flat $2 ROI':>15}")
    print("-" * 59)
    for bucket, n, wins, itm in cur.fetchall():
        win_pct = 100 * wins / n
        itm_pct = 100 * itm / n
        avg_odds = avg_odds_map.get(bucket, 5.0)
        spent = n * 2
        returned = wins * 2 * (avg_odds + 1)
        roi = 100 * (returned - spent) / spent
        marker = ' <<<' if roi > -5 else ''
        print(f"{bucket:<14}{n:>10,}{win_pct:>9.1f}%{itm_pct:>9.1f}%{roi:>13.1f}%{marker}")
    
    # Rank x odds matrix - ITM only (for brevity)
    print(f"\n--- {track}: ITM % matrix (rank × odds), n<20 hidden ---")
    cur.execute("""
        WITH ranked AS (
            SELECT 
                e.race_id, e.finish_pos, e.final_odds,
                RANK() OVER (PARTITION BY e.race_id ORDER BY e.final_odds) AS odds_rank
            FROM entries e
            JOIN races r ON e.race_id = r.id
            JOIN race_days rd ON r.race_day_id = rd.id
            JOIN tracks t ON rd.track_id = t.id
            WHERE t.code = ? AND e.final_odds IS NOT NULL
              AND r.field_size >= 4
              AND rd.race_date BETWEEN '2022-01-01' AND '2026-12-31'
        )
        SELECT 
            odds_rank,
            CASE 
                WHEN final_odds < 2 THEN '<2/1'
                WHEN final_odds < 4 THEN '2-4/1'
                WHEN final_odds < 6 THEN '4-6/1'
                WHEN final_odds < 10 THEN '6-10/1'
                WHEN final_odds < 20 THEN '10-20/1'
                ELSE '20+/1'
            END AS odds_bucket,
            COUNT(*) AS n,
            SUM(CASE WHEN finish_pos <= 3 THEN 1 ELSE 0 END) AS itm,
            SUM(CASE WHEN finish_pos = 1 THEN 1 ELSE 0 END) AS wins
        FROM ranked
        WHERE odds_rank <= 6
        GROUP BY odds_rank, odds_bucket
    """, (track,))
    
    results = {}
    for rank, bucket, n, itm, wins in cur.fetchall():
        results.setdefault(rank, {})[bucket] = (n, itm, wins)
    
    buckets = ['<2/1', '2-4/1', '4-6/1', '6-10/1', '10-20/1', '20+/1']
    print(f"{'Rank':<8}", end='')
    for b in buckets:
        print(f"{b:>13}", end='')
    print()
    print("-" * 86)
    for rank in range(1, 7):
        print(f"Rank {rank}: ", end='')
        for b in buckets:
            entry = results.get(rank, {}).get(b)
            if entry and entry[0] >= 20:
                n, itm, wins = entry
                itm_pct = 100 * itm / n
                print(f"  {itm_pct:>4.0f}% ({n:>4})", end='')
            else:
                print(f"             -", end='')
        print()

conn.close()