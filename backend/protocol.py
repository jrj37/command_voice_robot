"""Schémas Pydantic des messages WebSocket."""
from typing import Literal, Any, Optional, Dict
from pydantic import BaseModel


class ClientAction(BaseModel):
    type: Literal["action"]
    action: Literal["forward", "left", "right", "grab"]


class ClientAudio(BaseModel):
    type: Literal["audio_chunk"]
    # binary frames are handled separately; this is metadata-only fallback


class ClientReset(BaseModel):
    type: Literal["reset"]


class ClientAgent(BaseModel):
    type: Literal["agent"]
    target_type: str
    count: int = 0


class ClientAgentCancel(BaseModel):
    type: Literal["agent_cancel"]


ACTION_TO_INT = {"forward": 0, "left": 1, "right": 2, "grab": 3}


class ServerStaticInit(BaseModel):
    type: Literal["static"] = "static"
    payload: Dict[str, Any]


class ServerState(BaseModel):
    type: Literal["state"] = "state"
    payload: Dict[str, Any]


class ServerVoice(BaseModel):
    type: Literal["voice"] = "voice"
    text: str
    recognized: Optional[str] = None


class ServerError(BaseModel):
    type: Literal["error"] = "error"
    message: str
