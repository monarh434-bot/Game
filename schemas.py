from pydantic import BaseModel, Field
from typing import Literal

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
