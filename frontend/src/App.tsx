import { useEffect, useRef, useState } from "react";
import { GameSocket } from "./net/ws";
import { AudioRecorder } from "./audio/recorder";
import { GameCanvas } from "./game/GameCanvas";
import { MicPrompt } from "./ui/MicPrompt";
import { HUD } from "./ui/HUD";
import { LeftPanel, RightPanel } from "./ui/SidePanels";
import type { StaticPayload, StatePayload } from "./net/types";

export function App() {
  const wsRef = useRef<GameSocket | null>(null);
  const recRef = useRef<AudioRecorder | null>(null);
  const [connected, setConnected] = useState(false);
  const [started, setStarted] = useState(false);
  const [micActive, setMicActive] = useState(false);
  const [micLevel, setMicLevel] = useState(0);
  const [staticData, setStaticData] = useState<StaticPayload | null>(null);
  const [state, setState] = useState<StatePayload | null>(null);
  const [lastVoice, setLastVoice] = useState("");

  // ── WebSocket ──
  useEffect(() => {
    const ws = new GameSocket();
    wsRef.current = ws;
    ws.onStatus((c) => setConnected(c));
    ws.onMessage((msg) => {
      if (msg.type === "static") setStaticData(msg.payload);
      else if (msg.type === "state") setState(msg.payload);
      else if (msg.type === "voice") setLastVoice(msg.text);
    });
    ws.connect();
    return () => ws.close();
  }, []);

  // ── Keyboard ──
  useEffect(() => {
    if (!started) return;
    const handler = (e: KeyboardEvent) => {
      const ws = wsRef.current;
      if (!ws) return;
      switch (e.key) {
        case "ArrowUp": ws.send({ type: "action", action: "forward" }); break;
        case "ArrowLeft": ws.send({ type: "action", action: "left" }); break;
        case "ArrowRight": ws.send({ type: "action", action: "right" }); break;
        case " ": ws.send({ type: "action", action: "grab" }); e.preventDefault(); break;
        case "a": case "A": ws.send({ type: "agent", target_type: "clé", count: 0 }); break;
        case "r": case "R": ws.send({ type: "reset" }); break;
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [started]);

  const startWithMic = async () => {
    try {
      const rec = new AudioRecorder({
        onChunk: (buf) => wsRef.current?.sendBinary(buf),
        onFlush: () => wsRef.current?.send({ type: "flush_audio" }),
        onLevel: (rms) => setMicLevel(rms),
        onError: (e) => alert("Erreur micro : " + e.message),
      });
      await rec.start();
      recRef.current = rec;
      setMicActive(true);
      setStarted(true);
    } catch {
      // déjà signalé via onError
    }
  };

  const startKeyboardOnly = () => {
    setStarted(true);
  };

  if (!started) {
    return (
      <div className="app">
        <MicPrompt connected={connected} onActivate={startWithMic} onSkip={startKeyboardOnly} />
      </div>
    );
  }

  return (
    <div className="app">
      <div className="app-header">Command Voice Robot</div>
      <div className="game-shell">
        <LeftPanel state={state} />
        <div className="canvas-wrap">
          <GameCanvas staticData={staticData} state={state} />
          <HUD
            micActive={micActive}
            micLevel={micLevel}
            lastVoice={lastVoice}
            state={state}
            connected={connected}
          />
        </div>
        <RightPanel
          state={state}
          onReset={() => wsRef.current?.send({ type: "reset" })}
          onAgent={(target) => wsRef.current?.send({ type: "agent", target_type: target, count: 0 })}
          onCancelAgent={() => wsRef.current?.send({ type: "agent_cancel" })}
        />
      </div>
    </div>
  );
}
