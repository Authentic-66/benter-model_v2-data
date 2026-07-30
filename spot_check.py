"""
Phase 3C Spot-Check Script
Doug's tool for reviewing the entry_features_v1 table

Usage:
  cd D:\Benter Model_v2 Data\benter-model_v2-data
  python spot_check.py
"""
import sqlite3
import pandas as pd

# Adjust path if needed
DB_PATH = 'scripts/gp_full.db'

pd.set_option('display.max_columns', None)
pd.set_option('display.max_rows', None)
pd.set_option('display.width', 200)
pd.set_option('display.max_colwidth', 30)

conn = sqlite3.connect(DB_PATH)

# ============================================================
# STEP 1: Show 10 recent races to pick from
# ============================================================
print("=" * 80)
print("STEP 1: Recent GP races to spot-check")
print("=" * 80)

races = pd.read_sql("""
    SELECT r.id AS race_id, 
           rd.race_date, 
           r.race_num,
           r.distance_text,
           r.surface, 
           r.track_condition,
           r.field_size,
           r.race_type
    FROM races r
    JOIN race_days rd ON r.race_day_id = rd.id
    WHERE r.field_size BETWEEN 7 AND 10
      AND r.breed = 'Thoroughbred'
      AND rd.race_date >= '2026-01-01'
    ORDER BY rd.race_date DESC, r.race_num
    LIMIT 10
""", conn)
print(races.to_string(index=False))
print()

# ============================================================
# STEP 2: Pick the first race and dump ALL features
# ============================================================
race_id = int(races['race_id'].iloc[0])
race_info = races.iloc[0]

print("=" * 80)
print(f"STEP 2: Features for race_id={race_id}")
print(f"   {race_info['race_date']} R{race_info['race_num']} | "
      f"{race_info['distance_text']} {race_info['surface']} {race_info['track_condition']} | "
      f"{race_info['field_size']} horses")
print("=" * 80)

features = pd.read_sql(f"""
    SELECT * 
    FROM entry_features_v1 
    WHERE race_id = {race_id}
    ORDER BY post_position
""", conn)

# Transpose so features are rows, horses are columns
features_t = features.set_index('horse_name').T
print()
print(features_t.to_string())
print()

# ============================================================
# STEP 3: Sanity checks
# ============================================================
print("=" * 80)
print("STEP 3: Sanity checks")
print("=" * 80)

# Check 1: Favorite identification
if 'is_favorite' in features.columns and 'final_odds' in features.columns:
    fav = features[features['is_favorite'] == 1]
    lowest_odds = features['final_odds'].min()
    print(f"[Check 1] Favorite has is_favorite=1: {len(fav) == 1}")
    if len(fav) == 1:
        print(f"          Favorite odds={fav['final_odds'].iloc[0]}, "
              f"Field lowest={lowest_odds} (should match)")

# Check 2: Post positions
if 'post_position' in features.columns:
    posts = sorted(features['post_position'].dropna().tolist())
    expected = list(range(1, len(features) + 1))
    print(f"[Check 2] Post positions sequential 1..N: {posts == expected}")
    print(f"          Actual: {posts}")

# Check 3: First-time starters have NULL career stats
if 'career_starts' in features.columns and 'career_win_pct_shrunk' in features.columns:
    first_timers = features[features['career_starts'] == 0]
    print(f"[Check 3] First-time starters ({len(first_timers)} in this race): "
          f"career_win_pct_shrunk should be NULL")
    if len(first_timers) > 0:
        vals = first_timers['career_win_pct_shrunk'].tolist()
        print(f"          Values: {vals}")

# Check 4: Speed figure distribution
if 'last_race_speed_figure' in features.columns:
    speeds = features['last_race_speed_figure'].dropna()
    if len(speeds) > 0:
        print(f"[Check 4] Speed figure range: {speeds.min():.1f} to {speeds.max():.1f} "
              f"(should be roughly 40-110)")

# Check 5: Trainer/jockey shrunk stats reasonable (0 to 1)
for col in ['trainer_30d_winrate_shrunk', 'trainer_365d_winrate_shrunk', 
            'jockey_30d_winrate_shrunk']:
    if col in features.columns:
        vals = features[col].dropna()
        if len(vals) > 0:
            in_range = (vals.between(0, 1)).all()
            print(f"[Check 5] {col}: all in [0,1] range: {in_range}")
            print(f"          Range: {vals.min():.3f} to {vals.max():.3f}")

print()
print("=" * 80)
print("DONE. Review the features above and sanity checks.")
print("=" * 80)

conn.close()
