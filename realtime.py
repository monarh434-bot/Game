import json
from collections import defaultdict

class RoomManager:
    def __init__(self):
        self.rooms = defaultdict(dict)
        self.players = defaultdict(dict)
        self._counter = 0

    def next_id(self):
        self._counter += 1
        return f"p{self._counter}"

    async def connect(self, room: str, websocket, nickname: str):
        await websocket.accept()
        client_id = self.next_id()
        self.rooms[room][client_id] = websocket
        self.players[room][client_id] = {"id": client_id, "nickname": nickname, "x": 0, "y": 2, "z": 0}
        await self.broadcast(room, {"type": "player_join", "player": self.players[room][client_id], "players": list(self.players[room].values())})
        return client_id

    async def disconnect(self, room: str, client_id: str):
        self.rooms[room].pop(client_id, None)
        self.players[room].pop(client_id, None)
        await self.broadcast(room, {"type": "player_leave", "id": client_id, "players": list(self.players[room].values())})

    async def update_player(self, room: str, client_id: str, data: dict):
        player = self.players[room].get(client_id)
        if not player:
            return
        for key in ("x", "y", "z"):
            if key in data:
                try:
                    player[key] = float(data[key])
                except (TypeError, ValueError):
                    pass
        await self.broadcast(room, {"type": "player_sync", "players": list(self.players[room].values())})

    async def broadcast(self, room: str, payload: dict):
        dead = []
        for client_id, ws in self.rooms[room].items():
            try:
                await ws.send_text(json.dumps(payload))
            except Exception:
                dead.append(client_id)
        for client_id in dead:
            self.rooms[room].pop(client_id, None)
            self.players[room].pop(client_id, None)

manager = RoomManager()
