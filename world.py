from typing import Dict, Tuple, List
from db import load_blocks, upsert_block

class WorldState:
    def __init__(self):
        self.blocks: Dict[Tuple[int, int, int], str] = {}
        self.seed_world()

    def seed_world(self):
        for x in range(-8, 9):
            for z in range(-8, 9):
                self.blocks[(x, 0, z)] = "grass"
                if (x + z) % 5 == 0:
                    self.blocks[(x, 1, z)] = "stone"
        for b in load_blocks():
            self.blocks[(b["x"], b["y"], b["z"])] = b["block_type"]

    def list_blocks(self) -> List[dict]:
        return [{"x": x, "y": y, "z": z, "block_type": t} for (x, y, z), t in self.blocks.items()]

    def apply_block(self, x: int, y: int, z: int, block_type: str):
        key = (x, y, z)
        if block_type == "air":
            self.blocks.pop(key, None)
        else:
            self.blocks[key] = block_type
        upsert_block(x, y, z, block_type)
