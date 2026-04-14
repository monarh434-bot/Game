from pathlib import Path
import json
import sqlite3
from collections import defaultdict
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Literal

ROOT = Path(__file__).resolve().parent
DB_FILE = ROOT / "game.db"

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

def upsert_block(x, y, z, block_type):
    conn = get_conn()
    if block_type == "air":
        conn.execute("DELETE FROM blocks WHERE x=? AND y=? AND z=?", (x, y, z))
    else:
        conn.execute("INSERT OR REPLACE INTO blocks (x,y,z,block_type) VALUES (?,?,?,?)", (x, y, z, block_type))
    conn.commit()
    conn.close()

def load_ai_state():
    conn = get_conn()
    row = conn.execute("SELECT mood,intensity,memory_json FROM ai_state WHERE id=1").fetchone()
    conn.close()
    return {"mood": row["mood"], "intensity": row["intensity"], "memory": json.loads(row["memory_json"])}

def save_ai_state(mood, intensity, memory):
    conn = get_conn()
    conn.execute("UPDATE ai_state SET mood=?, intensity=?, memory_json=? WHERE id=1", (mood, intensity, json.dumps(memory)))
    conn.commit()
    conn.close()

class JoinRequest(BaseModel):
    nickname: str = Field(min_length=2, max_length=20)

class BlockUpdate(BaseModel):
    x: int
    y: int
    z: int
    block_type: Literal["grass", "stone", "wood", "air"]

class ChatMessage(BaseModel):
    nickname: str = Field(min_length=2, max_length=20)
    message: str = Field(min_length=1, max_length=200)

class WorldState:
    def __init__(self):
        self.blocks = {}
        self.seed_world()

    def seed_world(self):
        for x in range(-8, 9):
            for z in range(-8, 9):
                self.blocks[(x, 0, z)] = "grass"
                if (x + z) % 5 == 0:
                    self.blocks[(x, 1, z)] = "stone"
        for b in load_blocks():
            self.blocks[(b["x"], b["y"], b["z"])] = b["block_type"]

    def list_blocks(self):
        return [{"x": x, "y": y, "z": z, "block_type": t} for (x, y, z), t in self.blocks.items()]

    def apply_block(self, x, y, z, block_type):
        key = (x, y, z)
        if block_type == "air":
            self.blocks.pop(key, None)
        else:
            self.blocks[key] = block_type
        upsert_block(x, y, z, block_type)

class WorldAI:
    def __init__(self):
        state = load_ai_state()
        self.mood = state["mood"]
        self.intensity = state["intensity"]
        self.memory = state["memory"]

    def persist(self):
        save_ai_state(self.mood, self.intensity, self.memory)

    def observe(self, event_type, payload):
        self.memory["last_event"] = {"type": event_type, "payload": payload}
        self.memory["event_count"] = int(self.memory.get("event_count", 0)) + 1
        if event_type == "block_place":
            self.intensity = min(5, self.intensity + 1)
            self.mood = "alert" if self.intensity >= 3 else "curious"
        elif event_type == "block_remove":
            self.mood = "protective"
            self.intensity = min(5, self.intensity + 1)
        elif event_type == "chat":
            msg = payload.get("message", "").lower()
            if "hello" in msg or "hi" in msg:
                self.mood = "friendly"
            elif "attack" in msg or "destroy" in msg:
                self.mood = "defensive"
                self.intensity = min(5, self.intensity + 1)
        self.persist()

    def decide_event(self):
        if self.mood == "friendly":
            return {"type": "ai_message", "message": "The world spirit welcomes the builders."}
        if self.mood == "protective":
            return {"type": "world_event", "message": "The ground hardens as the spirit defends the land."}
        if self.intensity >= 4:
            return {"type": "world_event", "message": "A pulse moves through the world. The spirit is watching."}
        return {"type": "ai_message", "message": "The world spirit is observing quietly."}

class RoomManager:
    def __init__(self):
        self.rooms = defaultdict(dict)
        self.players = defaultdict(dict)
        self.counter = 0

    def next_id(self):
        self.counter += 1
        return f"p{self.counter}"

    async def connect(self, room, websocket, nickname):
        await websocket.accept()
        cid = self.next_id()
        self.rooms[room][cid] = websocket
        self.players[room][cid] = {"id": cid, "nickname": nickname, "x": 0, "y": 2, "z": 0}
        await self.broadcast(room, {"type": "player_join", "players": list(self.players[room].values())})
        return cid

    async def disconnect(self, room, cid):
        self.rooms[room].pop(cid, None)
        self.players[room].pop(cid, None)
        await self.broadcast(room, {"type": "player_leave", "players": list(self.players[room].values())})

    async def update_player(self, room, cid, data):
        player = self.players[room].get(cid)
        if not player:
            return
        for key in ("x", "y", "z"):
            if key in data:
                try:
                    player[key] = float(data[key])
                except Exception:
                    pass
        await self.broadcast(room, {"type": "player_sync", "players": list(self.players[room].values())})

    async def broadcast(self, room, payload):
        dead = []
        for cid, ws in self.rooms[room].items():
            try:
                await ws.send_text(json.dumps(payload))
            except Exception:
                dead.append(cid)
        for cid in dead:
            self.rooms[room].pop(cid, None)
            self.players[room].pop(cid, None)

app = FastAPI()
init_db()
world = WorldState()
ai = WorldAI()
manager = RoomManager()

@app.get("/")
def root():
    return FileResponse(ROOT / "index.html")

app.mount("/static", StaticFiles(directory=ROOT), name="static")

@app.get("/api/health")
def health():
    return {"ok": True}

@app.get("/api/world")
def get_world():
    return {"blocks": world.list_blocks(), "ai": {"mood": ai.mood, "intensity": ai.intensity}}

@app.post("/api/join")
def join(req: JoinRequest):
    return {"nickname": req.nickname, "room": "default"}

@app.post("/api/block")
def update_block(req: BlockUpdate):
    world.apply_block(req.x, req.y, req.z, req.block_type)
    ai.observe("block_remove" if req.block_type == "air" else "block_place", req.model_dump())
    return {"ok": True, "ai": ai.decide_event()}

@app.post("/api/chat")
def chat(req: ChatMessage):
    ai.observe("chat", req.model_dump())
    return {"ok": True, "ai": ai.decide_event()}

@app.websocket("/ws/{room}/{nickname}")
async def ws(websocket: WebSocket, room: str, nickname: str):
    cid = await manager.connect(room, websocket, nickname)
    await websocket.send_text(json.dumps({"type": "welcome", "id": cid, "world": world.list_blocks(), "ai": {"mood": ai.mood, "intensity": ai.intensity}}))
    try:
        while True:
            data = json.loads(await websocket.receive_text())
            t = data.get("type")
            if t == "move":
                await manager.update_player(room, cid, data)
            elif t == "chat":
                text = str(data.get("message", ""))[:200]
                ai.observe("chat", {"nickname": nickname, "message": text})
                await manager.broadcast(room, {"type": "chat", "nickname": nickname, "message": text})
                await manager.broadcast(room, ai.decide_event())
            elif t == "block":
                x, y, z = int(data["x"]), int(data["y"]), int(data["z"])
                block_type = str(data["block_type"])
                if block_type in {"grass", "stone", "wood", "air"}:
                    world.apply_block(x, y, z, block_type)
                    ai.observe("block_remove" if block_type == "air" else "block_place", data)
                    await manager.broadcast(room, {"type": "block", "x": x, "y": y, "z": z, "block_type": block_type})
                    await manager.broadcast(room, ai.decide_event())
    except WebSocketDisconnect:
        await manager.disconnect(room, cid)
