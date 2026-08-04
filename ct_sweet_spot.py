import sqlite3
conn = sqlite3.connect('scripts/racing_full.db')
cur = conn.cursor()

print("=" * 70)
print("CT 2022-2026: ITM RATE by final odds bucket (all horses)")
print("=" * 70)

cur.execute("""
    SELECT 
        CASE 
            WHEN final_odds < 1 THEN '01. < 1/1 (odds-on)'
            WHEN final_odds < 2 THEN '02. 1/1 - 1.99/1'
            WHEN final_odds < 3 THEN '03. 2/1 - 2.99/1'
            WHEN final_odds < 4 THEN '04. 3/1 - 3.99/1'
            WHEN final_odds < 5 THEN '05. 4/1 - 4.99/1'
            WHEN final_odds < 6 THEN '06. 5/1 - 5.99/1'
            WHEN final_odds < 8 THEN '07. 6/1 - 7.99/1'
            WHEN final_odds < 10 THEN '08. 8/1 - 9.99/1'
            WHEN final_odds < 15 THEN '09. 10/1 - 14.99/1'
            WHEN final_odds < 20 THEN '10. 15/1 - 19.99/1'
            WHEN final_odds < 30 THEN '11. 20/1 - 29.99/1'
            ELSE '12. 30/1+'
        END AS odds_bucket,
        COUNT(*) AS n_horses,
        SUM(CASE WHEN finish_pos = 1 THEN 1 ELSE 0 END) AS wins,
        SUM(CASE WHEN finish_pos <= 3 THEN 1 ELSE 0 END) AS itm
    FROM entries e
    JOIN races r ON e.race_id = r.id
    JOIN race_days rd ON r.race_day_id = rd.id
    JOIN tracks t ON rd.track_id = t.id
    WHERE t.code = 'CT' AND e.final_odds IS NOT NULL
      AND r.field_size >= 4
      AND rd.race_date BETWEEN '2022-01-01' AND '2026-12-31'
    GROUP BY odds_bucket
    ORDER BY odds_bucket
""")

print(f"\n{'Odds Range':<24}{'Horses':>10}{'Win %':>10}{'ITM %':>10}{'ITM Lift':>12}")
print("-" * 66)
overall_itm = 0
overall_horses = 0
data = []
for row in cur.fetchall():
    bucket, n, wins, itm = row
    win_pct = 100 * wins / n
    itm_pct = 100 * itm / n
    data.append((bucket, n, wins, itm, win_pct, itm_pct))
    overall_horses += n
    overall_itm += itm

base_itm_rate = 100 * overall_itm / overall_horses  # Should be ~3/avg_field_size

# Random baseline for field of 7.4 = 3/7.4 = 40.5%
random_baseline = 100 * 3 / 7.4

for bucket, n, wins, itm, win_pct, itm_pct in data:
    lift = itm_pct / random_baseline
    print(f"{bucket:<24}{n:>10,}{win_pct:>9.1f}%{itm_pct:>9.1f}%{lift:>10.2f}x")

print(f"\nRandom baseline (3 spots in field of 7.4): {random_baseline:.1f}%")
print(f"Overall ITM rate: {base_itm_rate:.1f}%")

# ROI simulation - flat $2 win bet
print()
print("=" * 70)
print("SIMULATED FLAT $2 WIN BET ROI by odds bucket")
print("=" * 70)

cur.execute("""
    SELECT 
        CASE 
            WHEN final_odds < 1 THEN '01. < 1/1 (odds-on)'
            WHEN final_odds < 2 THEN '02. 1/1 - 1.99/1'
            WHEN final_odds < 3 THEN '03. 2/1 - 2.99/1'
            WHEN final_odds < 4 THEN '04. 3/1 - 3.99/1'
            WHEN final_odds < 5 THEN '05. 4/1 - 4.99/1'
            WHEN final_odds < 6 THEN '06. 5/1 - 5.99/1'
            WHEN final_odds < 8 THEN '07. 6/1 - 7.99/1'
            WHEN final_odds < 10 THEN '08. 8/1 - 9.99/1'
            WHEN final_odds < 15 THEN '09. 10/1 - 14.99/1'
            WHEN final_odds < 20 THEN '10. 15/1 - 19.99/1'
            WHEN final_odds < 30 THEN '11. 20/1 - 29.99/1'
            ELSE '12. 30/1+'
        END AS odds_bucket,
        COUNT(*) AS n_horses,
        SUM(CASE WHEN finish_pos = 1 THEN 2 * final_odds ELSE 0 END) AS total_returned,
        SUM(CASE WHEN finish_pos = 1 THEN 1 ELSE 0 END) AS wins
    FROM entries e
    JOIN races r ON e.race_id = r.id
    JOIN race_days rd ON r.race_day_id = rd.id
    JOIN tracks t ON rd.track_id = t.id
    WHERE t.code = 'CT' AND e.final_odds IS NOT NULL
      AND r.field_size >= 4
      AND rd.race_date BETWEEN '2022-01-01' AND '2026-12-31'
    GROUP BY odds_bucket
    ORDER BY odds_bucket
""")

print(f"\n{'Odds Range':<24}{'Bets':>10}{'Wins':>8}{'$ Spent':>12}{'$ Returned':>14}{'ROI':>10}")
print("-" * 78)
for row in cur.fetchall():
    bucket, n, returned, wins = row
    spent = n * 2  # $2 per bet
    profit = returned - spent
    roi = 100 * profit / spent if spent else 0
    print(f"{bucket:<24}{n:>10,}{wins:>8,}{spent:>11,.0f}{returned:>13,.0f}{roi:>9.1f}%")

conn.close()