import sqlite3
import pandas as pd

pd.set_option('display.max_columns', 12)
pd.set_option('display.width', 200)

conn = sqlite3.connect('scripts/gp_full.db')

race_id = 14853

df = pd.read_sql(f"""
    SELECT h.name AS horse, 
           ef.post_position AS post,
           ef.final_odds AS odds,
           ef.is_favorite AS fav,
           ef.odds_rank_in_field AS odds_rank,
           ef.career_starts AS strts,
           ef.career_wins AS wins,
           ef.career_win_pct_shrunk AS car_win,
           ef.trainer_365d_winrate_shrunk AS trn_365,
           ef.jockey_365d_winrate_shrunk AS jky_365,
           ef.last_race_speed_figure AS spd_fig
    FROM entry_features_v1 ef
    JOIN horses h ON ef.horse_id = h.id
    WHERE ef.race_id = {race_id}
    ORDER BY ef.post_position
""", conn)

print(df.to_string(index=False))
conn.close()