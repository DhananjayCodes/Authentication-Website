import sqlite3, os
DB_NAME = "site.db"

conn = sqlite3.connect(DB_NAME)
cur = conn.cursor()

# Users table
cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password TEXT,
    name TEXT,
    dob TEXT,
    phone TEXT,
    profile_picture TEXT,
    token TEXT
)
""")

# Pages table
cur.execute("""
CREATE TABLE IF NOT EXISTS pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id)
)
""")

# Content table
cur.execute("""
CREATE TABLE IF NOT EXISTS content (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    page_id INTEGER NOT NULL,
    type TEXT NOT NULL,
    data TEXT NOT NULL,
    FOREIGN KEY(page_id) REFERENCES pages(id)
)
""")

# Shared permissions
cur.execute("""
CREATE TABLE IF NOT EXISTS shared (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    page_id INTEGER NOT NULL,
    shared_with INTEGER NOT NULL,
    FOREIGN KEY(page_id) REFERENCES pages(id),
    FOREIGN KEY(shared_with) REFERENCES users(id)
)
""")

conn.commit()
conn.close()
print("Database and tables ready!")
