import json
import sqlite3
from pathlib import Path

DB_FILE = Path(__file__).resolve().parent / "game.db"

def get_conn():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS blocks (
            x INTEGER NOT NULL,
            y INTEGER NOT NULL,
            z INTEGER NOT NULL,
            block_type TEXT NOT NULL,
            PRIMARY KEY (x, y, z)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ai_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            mood TEXT NOT NULL,
            intensity INTEGER NOT NULL,
            memory_json TEXT NOT NULL
        )
    """)
    cur.execute("""
        INSERT OR IGNORE INTO ai_state (id, mood, intensity, memory_json)
        VALUES (1, 'curious', 1, '{}')
    """)
    conn.commit()
    conn.close()

def load_blocks():
    conn = get_conn()
    rows = conn.execute("SELECT x,y,z,block_type FROM blocks").fetchall()
    conn.close()
    return [dict(row) for row in rows]

def upsert_block(x: int, y: int, z: int, block_type: str):
    conn = get_conn()
    if block_type == "air":
        conn.execute("DELETE FROM blocks WHERE x=? AND y=? AND z=?", (x, y, z))
    else:
        conn.execute(
            "INSERT OR REPLACE INTO blocks (x,y,z,block_type) VALUES (?,?,?,?)",
            (x, y, z, block_type)
        )
    conn.commit()
    conn.close()

def load_ai_state():
    conn = get_conn()
    row = conn.execute("SELECT mood,intensity,memory_json FROM ai_state WHERE id=1").fetchone()
    conn.close()
    return {
        "mood": row["mood"],
        "intensity": row["intensity"],
        "memory": json.loads(row["memory_json"]),
    }

def save_ai_state(mood: str, intensity: int, memory: dict):
    conn = get_conn()
    conn.execute(
        "UPDATE ai_state SET mood=?, intensity=?, memory_json=? WHERE id=1",
        (mood, intensity, json.dumps(memory))
    )
    conn.commit()
    conn.close()
