import sqlite3

conn = sqlite3.connect("users.db")
c = conn.cursor()
c.execute("SELECT COUNT(*) FROM users")
print("Total registered users:", c.fetchone()[0])
conn.close()

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    name TEXT,
    dob TEXT,
    phone TEXT,
    profile_picture TEXT DEFAULT 'uploads/default-avatar.png'
);
