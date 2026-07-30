import sqlite3
c = sqlite3.connect('scripts/gp_full.db')
cols = c.execute("PRAGMA table_info(entry_features_v1)").fetchall()
for i, col in enumerate(cols, 1):
    print(f"{i:3}. {col[1]}")