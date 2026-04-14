from pathlib import Path
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from db import init_db
from world import WorldState
from ai import WorldAI
from schemas import JoinRequest, BlockUpdate, ChatMessage
from realtime import manager

app = FastAPI(title="Voxel AI World Flat")
init_db()
world = WorldState()
ai = WorldAI.from_db()
ROOT = Path(__file__).resolve().parent

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

@app.get("/")
def root():
    return FileResponse(ROOT / "index.html")

app.mount("/static", StaticFiles(directory=ROOT), name="static")

@app.websocket("/ws/{room}/{nickname}")
async def websocket_endpoint(websocket: WebSocket, room: str, nickname: str):
    client_id = await manager.connect(room, websocket, nickname)
    await websocket.send_text(json.dumps({"type": "welcome", "id": client_id, "world": world.list_blocks(), "ai": {"mood": ai.mood, "intensity": ai.intensity}}))
    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            msg_type = data.get("type")
            if msg_type == "move":
                await manager.update_player(room, client_id, data)
            elif msg_type == "chat":
                text = str(data.get("message", ""))[:200]
                ai.observe("chat", {"nickname": nickname, "message": text})
                await manager.broadcast(room, {"type": "chat", "nickname": nickname, "message": text})
                await manager.broadcast(room, ai.decide_event())
            elif msg_type == "block":
                x, y, z = int(data["x"]), int(data["y"]), int(data["z"])
                block_type = str(data["block_type"])
                if block_type not in {"grass", "stone", "wood", "air"}:
                    continue
                world.apply_block(x, y, z, block_type)
                ai.observe("block_remove" if block_type == "air" else "block_place", data)
                await manager.broadcast(room, {"type": "block", "x": x, "y": y, "z": z, "block_type": block_type})
                await manager.broadcast(room, ai.decide_event())
    except WebSocketDisconnect:
        await manager.disconnect(room, client_id)
