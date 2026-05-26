import type { StatePayload } from "../net/types";

interface Props {
  micActive: boolean;
  micLevel: number;
  lastVoice: string;
  state: StatePayload | null;
  connected: boolean;
}

export function HUD({ micActive, micLevel, lastVoice, state, connected }: Props) {
  const levelOn = micLevel > 0.005;
  return (
    <>
      {!connected && <div className="disconnect-banner">⚠ DECONNECTE — Reconnexion en cours…</div>}
      <div className="hud-overlay">
        <div className={`hud-pill ${micActive ? "mic-on" : "mic-off"}`}>
          <span className="mic-indicator">
            <span className={`mic-dot ${micActive && levelOn ? "on" : ""}`}></span>
            {micActive ? "MIC ON" : "MIC OFF"}
          </span>
        </div>
        <div className="hud-pill">
          POS {state?.robot.x ?? "-"},{state?.robot.y ?? "-"} · {state?.robot.dir_name ?? ""}
        </div>
      </div>
      <div className="hud-bottom">
        <span className="hud-cmd">{lastVoice ? `🗣 "${lastVoice}"` : "🎤 …"}</span>
        {state?.agent.active && (
          <span className="hud-agent">🤖 {state.agent.status}</span>
        )}
      </div>
    </>
  );
}
