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
  if (!state) return <div className="side-panel"><h2>INVENTAIRE</h2></div>;
  const inv = state.inventory;
  return (
    <div className="side-panel">
      <h2>📦 INVENTAIRE</h2>
      <div className="inv-list">
        {Object.entries(inv).length === 0 && (
          <div style={{ gridColumn: "1/-1", color: "var(--text-dim)" }}>vide</div>
        )}
        {Object.entries(inv).map(([name, n]) => (
          <div className="inv-cell" key={name}>
            <span>{SHAPE_EMOJI[name] ?? "•"} {name}</span>
            <strong>{n}</strong>
          </div>
        ))}
      </div>
      <div style={{ marginTop: 16, fontSize: 18 }}>
        <div className="row"><span>Total</span><strong>{state.inventory_total} / {state.objects_total}</strong></div>
        {state.nearby.length > 0 && (
          <div className="row" style={{ color: "var(--warn)" }}>
            <span>À portée</span><strong>{state.nearby[0]}</strong>
          </div>
        )}
      </div>
    </div>
  );
}

export function RightPanel({ state, onReset, onAgent, onCancelAgent }: Props) {
  return (
    <div className="side-panel">
      <h2>🤖 AGENT IA</h2>
      {state?.agent.active ? (
        <>
          <div style={{ fontSize: 18, marginBottom: 12 }}>
            <div>🎯 <strong>{state.agent.target_type}</strong></div>
            <div style={{ color: "var(--text-dim)" }}>{state.agent.status}</div>
            <div style={{ marginTop: 8 }}>
              Collectés : <strong>{state.agent.collected}</strong>
              {state.agent.max_collect > 0 && ` / ${state.agent.max_collect}`}
            </div>
          </div>
          <button className="btn btn-sm btn-pink" onClick={onCancelAgent}>STOP AGENT</button>
        </>
      ) : (
        <div className="btn-row">
          <button className="btn btn-sm" onClick={() => onAgent("clé")}>Clés</button>
          <button className="btn btn-sm" onClick={() => onAgent("gemme")}>Gemmes</button>
          <button className="btn btn-sm" onClick={() => onAgent("étoile")}>Étoiles</button>
          <button className="btn btn-sm" onClick={() => onAgent("all")}>Tout</button>
        </div>
      )}

      <h2 style={{ marginTop: 24 }}>⚙️ CONTROLE</h2>
      <div className="controls-help">
        <div><kbd>↑</kbd> avancer</div>
        <div><kbd>←</kbd> gauche · <kbd>→</kbd> droite</div>
        <div><kbd>Espace</kbd> ramasser</div>
        <div><kbd>R</kbd> reset</div>
      </div>
      <div style={{ marginTop: 16 }}>
        <button className="btn btn-sm" onClick={onReset}>🔄 RESET</button>
      </div>
    </div>
  );
}
