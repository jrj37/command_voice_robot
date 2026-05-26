"""Serveur FastAPI : WebSocket /ws — relais audio + état du jeu."""
from __future__ import annotations

import asyncio
import json
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from game.env import RobotEnv
from game.agent import RobotAgent
from voice import commands as cmds
from voice.recognizer import WhisperRecognizer
from protocol import ACTION_TO_INT


# Whisper model peut être lourd à charger — fait une fois au démarrage
_recognizer: WhisperRecognizer | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _recognizer
    model = os.environ.get("WHISPER_MODEL", "small")
    _recognizer = WhisperRecognizer(model_name=model)
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"status": "ok", "service": "robot voice control"}


AGENT_TICK_INTERVAL = 0.12  # secondes — ralentit l'agent pour voir les mouvements
AUDIO_FLUSH_THRESHOLD = 16000 * 2 * 2  # 2 secondes à 16 kHz int16
SAMPLE_RATE = 16000


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    env = RobotEnv()
    agent = RobotAgent()
    audio_buffer = bytearray()

    # Envoyer l'init statique
    await ws.send_json({"type": "static", "payload": env.serialize_static()})
    await send_state(ws, env, agent)

    async def send_voice(text: str, recognized: str | None):
        await ws.send_json({"type": "voice", "text": text, "recognized": recognized})

    async def transcribe_and_apply():
        """Vidange le buffer audio, transcrit, applique la commande."""
        nonlocal audio_buffer
        if not _recognizer or len(audio_buffer) < SAMPLE_RATE:  # < 0.5s
            audio_buffer = bytearray()
            return
        pcm = bytes(audio_buffer)
        audio_buffer = bytearray()
        loop = asyncio.get_event_loop()
        text = await loop.run_in_executor(None, _recognizer.transcribe_pcm16, pcm, SAMPLE_RATE)
        if not text:
            return
        parsed = cmds.parse(text)
        recognized = None
        if parsed.kind == "action":
            recognized = f"action:{parsed.action}"
            if agent.active:
                agent.cancel(env)
            env.step(parsed.action)
        elif parsed.kind == "agent":
            recognized = f"agent:{parsed.target_type} x{parsed.count}"
            agent.start_mission(env, parsed.target_type, parsed.count)
        elif parsed.kind == "hint":
            recognized = f"hint:{parsed.landmark}"
            if agent.active:
                agent.give_hint(env, parsed.landmark)
        elif parsed.kind == "stop":
            recognized = "stop"
            agent.cancel(env)
            env.reset()
        await send_voice(text, recognized)
        await send_state(ws, env, agent)

    async def agent_loop():
        """Tâche d'arrière-plan : tick de l'agent à intervalle régulier."""
        while True:
            await asyncio.sleep(AGENT_TICK_INTERVAL)
            if agent.active:
                action = agent.tick(env)
                if action is not None:
                    env.step(action)
                await send_state(ws, env, agent)

    agent_task = asyncio.create_task(agent_loop())

    try:
        while True:
            msg = await ws.receive()
            if "bytes" in msg and msg["bytes"]:
                audio_buffer.extend(msg["bytes"])
                if len(audio_buffer) >= AUDIO_FLUSH_THRESHOLD:
                    asyncio.create_task(transcribe_and_apply())
            elif "text" in msg and msg["text"]:
                try:
                    data = json.loads(msg["text"])
                except json.JSONDecodeError:
                    continue
                mtype = data.get("type")
                if mtype == "action":
                    act = ACTION_TO_INT.get(data.get("action"))
                    if act is not None:
                        if agent.active and act != 3:
                            agent.cancel(env)
                        env.step(act)
                        await send_state(ws, env, agent)
                elif mtype == "reset":
                    agent.cancel(env)
                    env.reset()
                    await ws.send_json({"type": "static", "payload": env.serialize_static()})
                    await send_state(ws, env, agent)
                elif mtype == "agent":
                    agent.start_mission(env, data.get("target_type", "all"), data.get("count", 0))
                    await send_state(ws, env, agent)
                elif mtype == "agent_cancel":
                    agent.cancel(env)
                    await send_state(ws, env, agent)
                elif mtype == "flush_audio":
                    asyncio.create_task(transcribe_and_apply())
    except WebSocketDisconnect:
        pass
    finally:
        agent_task.cancel()


async def send_state(ws: WebSocket, env: RobotEnv, agent: RobotAgent):
    payload = env.serialize_state()
    payload["agent"] = agent.serialize()
    try:
        await ws.send_json({"type": "state", "payload": payload})
    except Exception:
        pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
