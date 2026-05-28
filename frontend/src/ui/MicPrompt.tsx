interface Props {
  connected: boolean;
  onActivate: () => void;
  onSkip: () => void;
}

export function MicPrompt({ connected, onActivate, onSkip }: Props) {
  return (
    <div className="mic-prompt">
      <div className="pulse">🎙️</div>
      <div>
        <h1>Command Voice Robot</h1>
        <p style={{ marginTop: 14 }}>
          Pilote le robot à la voix. Dis <strong>avance</strong>, <strong>gauche</strong>,{" "}
          <strong>droite</strong>, <strong>ramasse</strong>, ou <strong>cherche les clés</strong>.
          <br />
          Reconnaissance Whisper · backend Python.
        </p>
      </div>
      <div className="btn-row">
        <button className="btn" disabled={!connected} onClick={onActivate}>
          {connected ? "🎤  Activer le micro" : "Connexion en cours…"}
        </button>
        <button className="btn btn-secondary" onClick={onSkip}>
          Jouer au clavier
        </button>
      </div>
      <div className="controls-help" style={{ gridTemplateColumns: "1fr 1fr", display: "grid" }}>
        <div className="ctrl-row"><kbd>↑</kbd> avancer</div>
        <div className="ctrl-row"><kbd>Espace</kbd> ramasser</div>
        <div className="ctrl-row"><kbd>←</kbd> <kbd>→</kbd> tourner</div>
        <div className="ctrl-row"><kbd>R</kbd> reset</div>
      </div>
    </div>
  );
}
