import type { StatePayload } from "../net/types";

const SHAPE_EMOJI: Record<string, string> = {
  "clé": "🔑",
  "gemme": "💎",
  "étoile": "⭐",
  "pièce": "🪙",
  "batterie": "🔋",
};

interface Props {
  state: StatePayload | null;
  onReset: () => void;
  onAgent: (target: string) => void;
  onCancelAgent: () => void;
}

export function LeftPanel({ state }: { state: StatePayload | null }) {
  const inv = state?.inventory ?? {};
  const total = state?.inventory_total ?? 0;
  const max = state?.objects_total ?? 0;
  const pct = max > 0 ? (total / max) * 100 : 0;

  return (
    <div className="side-panel">
      <div className="panel-title">
        <span className="dot" />
        Inventaire
      </div>

      <div className="inv-grid">
        {Object.keys(inv).length === 0 ? (
          <div className="inv-empty">aucun objet collecté</div>
        ) : (
          Object.entries(inv).map(([name, n]) => (
            <div className="inv-cell" key={name}>
              <span className="label">
                <span>{SHAPE_EMOJI[name] ?? "•"}</span>
                <span>{name}</span>
              </span>
              <span className="count">{n}</span>
            </div>
          ))
        )}
      </div>

      <div className="panel-section">
        <div className="stat-row">
          <span>Progression</span>
          <strong>{total} / {max}</strong>
        </div>
        <div className="progress">
          <div className="progress-bar" style={{ width: `${pct}%` }} />
        </div>
      </div>

      {state && state.nearby.length > 0 && (
        <div className="panel-section">
          <div className="stat-row">
            <span>À portée</span>
            <strong style={{ color: "var(--amber)" }}>{state.nearby[0]}</strong>
          </div>
        </div>
      )}

      {state && (
        <div className="panel-section">
          <div className="stat-row">
            <span>Position</span>
            <strong>{state.robot.x},{state.robot.y}</strong>
          </div>
          <div className="stat-row">
            <span>Cap</span>
            <strong>{state.robot.dir_name}</strong>
          </div>
        </div>
      )}
    </div>
  );
}

export function RightPanel({ state, onReset, onAgent, onCancelAgent }: Props) {
  return (
    <div className="side-panel">
      <div className="panel-title">
        <span className="dot" style={{ background: "var(--pink)", boxShadow: "0 0 8px var(--pink)" }} />
        Agent IA
      </div>

      {state?.agent.active ? (
        <div className="agent-card">
          <div className="target">🎯 {state.agent.target_type}</div>
          <div className="status">{state.agent.status}</div>
          <div className="progress-line">
            collectés : {state.agent.collected}
            {state.agent.max_collect > 0 && ` / ${state.agent.max_collect}`}
          </div>
          <button className="btn btn-pink btn-sm" onClick={onCancelAgent} style={{ width: "100%" }}>
            ⏹ Arrêter l'agent
          </button>
        </div>
      ) : (
        <div className="btn-grid">
          <button className="btn btn-secondary btn-sm" onClick={() => onAgent("clé")}>🔑 Clés</button>
          <button className="btn btn-secondary btn-sm" onClick={() => onAgent("gemme")}>💎 Gemmes</button>
          <button className="btn btn-secondary btn-sm" onClick={() => onAgent("étoile")}>⭐ Étoiles</button>
          <button className="btn btn-sm" onClick={() => onAgent("all")}>✨ Tout</button>
        </div>
      )}

      <div className="panel-section">
        <div className="panel-title" style={{ marginBottom: 12 }}>
          <span className="dot" style={{ background: "var(--cyan)", boxShadow: "0 0 8px var(--cyan)" }} />
          Contrôles
        </div>
        <div className="controls-help">
          <div className="ctrl-row"><kbd>↑</kbd><span>avancer d'une case</span></div>
          <div className="ctrl-row"><kbd>←</kbd><kbd>→</kbd><span>tourner</span></div>
          <div className="ctrl-row"><kbd>Espace</kbd><span>ramasser</span></div>
          <div className="ctrl-row"><kbd>R</kbd><span>reset</span></div>
        </div>
      </div>

      <div className="panel-section">
        <button className="btn btn-secondary btn-sm" onClick={onReset} style={{ width: "100%" }}>
          ↻ Reset la partie
        </button>
      </div>
    </div>
  );
}
