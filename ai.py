from dataclasses import dataclass, field
from typing import Dict, Any
from db import load_ai_state, save_ai_state

@dataclass
class WorldAI:
    mood: str = "curious"
    intensity: int = 1
    memory: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_db(cls):
        state = load_ai_state()
        return cls(mood=state["mood"], intensity=state["intensity"], memory=state["memory"])

    def persist(self):
        save_ai_state(self.mood, self.intensity, self.memory)

    def observe(self, event_type: str, payload: dict):
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
            return {"type": "world_event", "message": "The ground hardens as the spirit defends the land.", "effect": "stone_blessing"}
        if self.intensity >= 4:
            return {"type": "world_event", "message": "A pulse moves through the world. The spirit is watching.", "effect": "shockwave"}
        return {"type": "ai_message", "message": "The world spirit is observing quietly."}
