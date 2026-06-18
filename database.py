import sqlite3
from datetime import datetime
from collections import Counter

DB_NAME = "bot_database.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT,
            nickname TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS nicknames (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nickname TEXT UNIQUE NOT NULL
        )
    """)
    cursor.execute("SELECT COUNT(*) FROM nicknames")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO nicknames (nickname) VALUES (?)", ("Dobry_p2p",))
    conn.commit()
    conn.close()

def get_all_nicknames():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT nickname FROM nicknames ORDER BY nickname")
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]

def add_nickname(nickname):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO nicknames (nickname) VALUES (?)", (nickname,))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def delete_nickname(nickname):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM nicknames WHERE nickname = ?", (nickname,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def save_user(user_id, username, nickname):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (user_id, username, nickname, timestamp) VALUES (?, ?, ?, ?)",
        (user_id, username, nickname, datetime.now().strftime("%d.%m.%Y %H:%M:%S"))
    )
    conn.commit()
    conn.close()

def get_all_users():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, nickname, timestamp FROM users ORDER BY timestamp DESC")
    rows = cursor.fetchall()
    conn.close()
    return [{"user_id": r[0], "username": r[1], "nickname": r[2], "timestamp": r[3]} for r in rows]

def get_stats():
    users = get_all_users()
    total = len(users)
    nicknames = [u["nickname"] for u in users]
    popular = Counter(nicknames).most_common(5)
    return total, popular

def find_user_by_id(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, nickname, timestamp FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"user_id": row[0], "username": row[1], "nickname": row[2], "timestamp": row[3]}
    return None

def find_user_by_username(username):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, username, nickname, timestamp FROM users WHERE username LIKE ?", (f"%{username}%",))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"user_id": row[0], "username": row[1], "nickname": row[2], "timestamp": row[3]}
    return None

def export_csv():
    import csv
    from io import StringIO
    users = get_all_users()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["User ID", "Username", "Nickname", "Timestamp"])
    for u in users:
        writer.writerow([u["user_id"], u["username"], u["nickname"], u["timestamp"]])
    return output.getvalue()