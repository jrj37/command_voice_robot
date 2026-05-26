# 🤖 Command Voice Robot

Jeu de contrôle vocal d'un robot sur une grille — architecture **client / serveur** :

- 🐍 **Backend Python** (FastAPI + WebSocket) : logique du jeu + reconnaissance vocale Whisper
- ⚛️ **Frontend TypeScript** (React + Vite + Pixi.js) : rendu pixel art rétro 16-bit dans le navigateur

## ✨ Fonctionnalités

- 🎤 Reconnaissance vocale en français (Whisper local, sans clé API)
- 🤖 Agent IA autonome : exploration avec champ de vision limité + pathfinding BFS
- 💡 Indices vocaux pour guider l'agent ("près de la fontaine")
- 🎨 Rendu pixel art animé avec halos, particules au ramassage, fog of war
- 🌐 Interface web responsive (HUD overlay, panneaux latéraux)
- ⌨️ Contrôle clavier en alternative à la voix

## 🗣️ Commandes vocales

| Commande | Action |
|----------|--------|
| `avance`, `forward` | Le robot avance |
| `gauche`, `droite` | Tourner |
| `ramasse`, `attrape` | Attraper un objet proche |
| `cherche les clés`, `récupère 3 gemmes` | Lance l'agent IA |
| `près de la fontaine` | Indice à l'agent |
| `stop`, `quitter` | Reset |

Objets : `clé`, `gemme`, `étoile`, `pièce`, `batterie` (ou `tout`)
Repères : `fontaine`, `statue`, `banc`, `lampadaire`, `panneau`

## ⌨️ Raccourcis clavier

| Touche | Action |
|--------|--------|
| `↑` `←` `→` | Déplacer / tourner |
| `Espace` | Ramasser |
| `A` | Lancer l'agent IA sur les clés |
| `R` | Reset |

## 📦 Installation

### Prérequis
- Python 3.9+
- Node.js 18+
- Un microphone (autorisation navigateur)

### Backend

```bash
cd backend
python3 -m venv ../.venv
source ../.venv/bin/activate
pip install -r requirements.txt
```

### Frontend

```bash
cd frontend
npm install
```

## 🚀 Lancement

**Deux terminaux** :

```bash
# Terminal 1 — backend (port 8000)
cd backend
../.venv/bin/python main.py
```

```bash
# Terminal 2 — frontend (port 5173)
cd frontend
npm run dev
```

Puis ouvre <http://localhost:5173>.

Le frontend proxifie automatiquement le WebSocket `/ws` vers le backend via Vite.

Variable optionnelle pour changer le modèle Whisper (par défaut `small`) :
```bash
WHISPER_MODEL=base python main.py
```

## 🏗️ Architecture

```
┌─────────────────────────────┐         WebSocket           ┌──────────────────────────────┐
│   FRONTEND (TypeScript)     │ ◄──────── /ws ───────────► │   BACKEND (Python)           │
│                             │                              │                              │
│   React + Vite + Pixi.js    │   → audio chunks (PCM 16k)   │   FastAPI + websockets       │
│   Pixel art rendering       │   → actions / agent          │   Whisper (reconnaissance)   │
│   Web Audio (AudioWorklet)  │   ← state JSON               │   RobotEnv (logique pure)    │
│                             │   ← voice transcriptions     │   RobotAgent (BFS + vision)  │
└─────────────────────────────┘                              └──────────────────────────────┘
```

### Backend (`backend/`)

| Fichier | Rôle |
|---------|------|
| `main.py` | Serveur FastAPI, route WebSocket `/ws`, boucle agent |
| `game/env.py` | `RobotEnv` headless (logique de jeu) |
| `game/agent.py` | Agent IA (BFS, vision limitée, hints) |
| `game/objects.py` | Entités collectables + repères |
| `voice/commands.py` | Parser texte → commande (fuzzy matching) |
| `voice/recognizer.py` | Wrapper Whisper, transcription PCM |
| `protocol.py` | Schémas Pydantic des messages WS |

### Frontend (`frontend/src/`)

| Fichier | Rôle |
|---------|------|
| `App.tsx` | Layout principal, WS, clavier |
| `game/GameCanvas.tsx` | Composant Pixi.js |
| `game/renderer.ts` | Rendu pixel art (tilemap, sprites, anims, particles) |
| `ui/HUD.tsx` | Overlay micro + position + commande |
| `ui/MicPrompt.tsx` | Écran d'activation initial |
| `ui/SidePanels.tsx` | Inventaire + contrôles agent |
| `net/ws.ts` | Client WebSocket typé (reconnect auto) |
| `audio/recorder.ts` | Capture micro + VAD + envoi PCM 16 kHz |

## 🧪 Tests

```bash
# Backend
cd backend
../.venv/bin/python -m pytest

# Frontend (typecheck)
cd frontend
npx tsc --noEmit
```

## 📜 Licence

[MIT](LICENSE) © jrj37
