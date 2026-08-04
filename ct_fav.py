import sqlite3
conn = sqlite3.connect('scripts/racing_full.db')
cur = conn.cursor()

cur.execute("""
    WITH ranked AS (
        SELECT 
            e.race_id, e.finish_pos, e.final_odds,
            RANK() OVER (PARTITION BY e.race_id ORDER BY e.final_odds) AS odds_rank
        FROM entries e
        JOIN races r ON e.race_id = r.id
        JOIN race_days rd ON r.race_day_id = rd.id
        JOIN tracks t ON rd.track_id = t.id
        WHERE t.code = 'CT'
          AND e.final_odds IS NOT NULL
          AND r.field_size >= 4
          AND rd.race_date BETWEEN '2022-01-01' AND '2026-12-31'
    )
    SELECT 
        COUNT(DISTINCT race_id) AS total_races,
        SUM(CASE WHEN odds_rank=1 AND finish_pos=1 THEN 1 ELSE 0 END) AS won,
        SUM(CASE WHEN odds_rank=1 AND finish_pos=2 THEN 1 ELSE 0 END) AS second,
        SUM(CASE WHEN odds_rank=1 AND finish_pos=3 THEN 1 ELSE 0 END) AS third,
        SUM(CASE WHEN odds_rank=1 AND finish_pos<=3 THEN 1 ELSE 0 END) AS itm
    FROM ranked
""")
total, won, second, third, itm = cur.fetchone()
print(f"CT 2022-2026 (field size 4+): {total:,} races")
print(f"Favorite WON:      {won:,} ({100*won/total:.1f}%)")
print(f"Favorite 2nd:      {second:,} ({100*second/total:.1f}%)")
print(f"Favorite 3rd:      {third:,} ({100*third/total:.1f}%)")
print(f"Favorite ITM:      {itm:,} ({100*itm/total:.1f}%)")
conn.close()