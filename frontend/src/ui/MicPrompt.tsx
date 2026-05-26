interface Props {
  connected: boolean;
  onActivate: () => void;
  onSkip: () => void;
}

export function MicPrompt({ connected, onActivate, onSkip }: Props) {
  return (
    <div className="mic-prompt">
      <div className="pulse">🎤</div>
      <h1>COMMAND VOICE ROBOT</h1>
      <p>
        Ce jeu se contrôle à la voix. Parlez : <strong>avance</strong>, <strong>gauche</strong>,{" "}
        <strong>droite</strong>, <strong>ramasse</strong>, <strong>cherche les clés</strong>…
        <br />
        Reconnaissance via Whisper (backend Python).
      </p>
      <div className="btn-row">
        <button className="btn" disabled={!connected} onClick={onActivate}>
          {connected ? "Activer le micro" : "Connexion…"}
        </button>
        <button className="btn btn-pink" onClick={onSkip}>
          Jouer au clavier
        </button>
      </div>
      <div className="controls-help">
        <kbd>↑</kbd> avancer · <kbd>←</kbd> gauche · <kbd>→</kbd> droite ·{" "}
        <kbd>Espace</kbd> ramasser · <kbd>A</kbd> agent IA · <kbd>R</kbd> reset
      </div>
    </div>
  );
}
