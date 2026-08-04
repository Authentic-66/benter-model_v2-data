import sqlite3
conn = sqlite3.connect('scripts/racing_full.db')
cur = conn.cursor()

# Odds rank distribution for ITM spots (positions 1, 2, 3)
print("=" * 70)
print("CT 2022-2026: Who fills each ITM spot? (by tote odds rank)")
print("=" * 70)

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
        finish_pos,
        odds_rank,
        COUNT(*) AS n
    FROM ranked
    WHERE finish_pos IN (1,2,3) AND odds_rank <= 8
    GROUP BY finish_pos, odds_rank
    ORDER BY finish_pos, odds_rank
""")

results = {}
for fp, orank, n in cur.fetchall():
    results.setdefault(fp, {})[orank] = n

for pos in [1, 2, 3]:
    total = sum(results.get(pos, {}).values())
    print(f"\n{pos}-place finishers by odds rank:")
    for orank in range(1, 9):
        n = results.get(pos, {}).get(orank, 0)
        pct = 100 * n / total if total else 0
        bar = '█' * int(pct / 2)
        print(f"  Rank {orank}: {n:>5} ({pct:>4.1f}%) {bar}")

# Actual odds ranges of ITM non-favorites  
print()
print("=" * 70)
print("What are actual odds of non-favorite ITM finishers?")
print("=" * 70)

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
        finish_pos,
        CASE 
            WHEN final_odds < 2 THEN '< 2/1 (heavy fav)'
            WHEN final_odds < 4 THEN '2/1 - 3.99/1'
            WHEN final_odds < 6 THEN '4/1 - 5.99/1'
            WHEN final_odds < 10 THEN '6/1 - 9.99/1'
            WHEN final_odds < 20 THEN '10/1 - 19.99/1'
            ELSE '20/1+'
        END AS odds_range,
        COUNT(*) AS n
    FROM ranked
    WHERE finish_pos IN (1,2,3) AND odds_rank > 1
    GROUP BY finish_pos, odds_range
    ORDER BY finish_pos, MIN(final_odds)
""")

buckets = {}
for fp, orange, n in cur.fetchall():
    buckets.setdefault(fp, {})[orange] = n

order = ['< 2/1 (heavy fav)', '2/1 - 3.99/1', '4/1 - 5.99/1', 
         '6/1 - 9.99/1', '10/1 - 19.99/1', '20/1+']

for pos in [1, 2, 3]:
    total = sum(buckets.get(pos, {}).values())
    print(f"\n{pos}-place NON-FAVORITE finishers by odds bucket:")
    for orange in order:
        n = buckets.get(pos, {}).get(orange, 0)
        pct = 100 * n / total if total else 0
        print(f"  {orange:<22}: {n:>5} ({pct:>4.1f}%)")

# Answer the >4/1 question
print()
print("=" * 70)
print("QUESTION: Can we predict >4/1 horses for ITM spots?")
print("=" * 70)

cur.execute("""
    WITH ranked AS (
        SELECT 
            e.race_id, e.finish_pos, e.final_odds
        FROM entries e
        JOIN races r ON e.race_id = r.id
        JOIN race_days rd ON r.race_day_id = rd.id
        JOIN tracks t ON rd.track_id = t.id
        WHERE t.code = 'CT' AND e.final_odds IS NOT NULL
          AND r.field_size >= 4
          AND rd.race_date BETWEEN '2022-01-01' AND '2026-12-31'
    )
    SELECT 
        COUNT(*) AS n_over_4to1,
        SUM(CASE WHEN finish_pos <= 3 THEN 1 ELSE 0 END) AS n_itm,
        SUM(CASE WHEN finish_pos = 1 THEN 1 ELSE 0 END) AS n_won
    FROM ranked
    WHERE final_odds >= 4
""")
n_horses, n_itm, n_won = cur.fetchone()
print(f"\nAll horses at CT with final odds >= 4/1:")
print(f"  Total horses: {n_horses:,}")
print(f"  Finished ITM: {n_itm:,} ({100*n_itm/n_horses:.1f}%)")
print(f"  Won:          {n_won:,} ({100*n_won/n_horses:.1f}%)")

# Field size context
cur.execute("""
    SELECT AVG(field_size), MIN(field_size), MAX(field_size)
    FROM races r 
    JOIN race_days rd ON r.race_day_id = rd.id
    JOIN tracks t ON rd.track_id = t.id
    WHERE t.code = 'CT' 
      AND rd.race_date BETWEEN '2022-01-01' AND '2026-12-31'
      AND r.field_size >= 4
""")
avg_fs, min_fs, max_fs = cur.fetchone()
print(f"\nContext - CT field sizes: avg {avg_fs:.1f}, range {min_fs}-{max_fs}")

conn.close()