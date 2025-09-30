# migrate.py
import sqlite3
conn = sqlite3.connect("users.db")
c = conn.cursor()
# add is_admin if missing
try:
    c.execute("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0")
except:
    pass
c.execute("CREATE TABLE IF NOT EXISTS pages (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, title TEXT, description TEXT)")
c.execute("CREATE TABLE IF NOT EXISTS content (id INTEGER PRIMARY KEY AUTOINCREMENT, page_id INTEGER, type TEXT, data TEXT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP)")
c.execute("CREATE TABLE IF NOT EXISTS permissions (id INTEGER PRIMARY KEY AUTOINCREMENT, page_id INTEGER, allowed_user_id INTEGER)")
conn.commit()
conn.close()
print("Migration done")
