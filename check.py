import sqlite3
c = sqlite3.connect('scripts/gp_full.db')
tables = c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print([t[0] for t in tables])