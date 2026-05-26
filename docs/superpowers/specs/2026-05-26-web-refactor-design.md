# Refonte web — Backend Python + Frontend TypeScript

**Date** : 2026-05-26
**Statut** : Design approuvé

## Objectif

Refondre l'application `command_voice_robot` (actuellement monolithique en Python/Pygame) en architecture client-serveur :

- **Backend Python** : logique du jeu + reconnaissance vocale Whisper
- **Frontend TypeScript** : rendu pixel art rétro + UI moderne dans le navigateur

Le jeu reste le même (robot sur grille 11×11, commandes vocales, agent IA), mais avec un nouveau design visuel et une stack web.

## Architecture

```
┌─────────────────────────────┐         WebSocket           ┌──────────────────────────────┐
│   FRONTEND (TypeScript)     │ ◄──────── ws://… ────────► │   BACKEND (Python)           │
│                             │                              │                              │
│   • React + Vite            │   → audio chunks (PCM)       │   • FastAPI + websockets     │
│   • Pixi.js (rendu jeu)     │   → key actions              │   • Whisper (reconnaissance) │
│   • React HUD/UI            │   ← game_state (JSON)        │   • RobotEnv (logique jeu)   │
│   • Web Audio (capture mic) │   ← voice_event              │   • RobotAgent (IA)          │
└─────────────────────────────┘                              └──────────────────────────────┘
```

## Choix techniques

| Aspect | Choix | Raison |
|--------|-------|--------|
| Voice recognition | Backend Python (Whisper local) | Précision, déjà éprouvé |
| Frontend framework | React + Vite | Stack moderne, HMR rapide, écosystème |
| Rendu jeu | Pixi.js (WebGL) | Perfs 2D, animations fluides |
| Style visuel | Pixel art rétro 16-bit | Charme, adapté à une grille |
| Protocole | WebSocket bidirectionnel | Temps réel, audio streaming |
| Serveur | FastAPI + websockets | Async natif, typage Pydantic |
| Tests | pytest (back), vitest (front) | Standards de chaque écosystème |

## Découpage modulaire

### Backend (`backend/`)

| Fichier | Rôle |
|---------|------|
| `main.py` | Serveur FastAPI, route WebSocket `/ws` |
| `game/env.py` | `RobotEnv` headless (logique pure, sans Pygame) |
| `game/agent.py` | Agent IA (pathfinding, collecte) |
| `game/objects.py` | Entités (clés, gemmes, repères…) |
| `voice/recognizer.py` | Wrapper Whisper, traite chunks audio |
| `voice/commands.py` | Parser texte → action / mission |
| `protocol.py` | Schémas Pydantic des messages WS |
| `tests/` | Tests pytest |
| `requirements.txt` | Dépendances |

### Frontend (`frontend/`)

| Fichier | Rôle |
|---------|------|
| `src/main.tsx` | Entrypoint React |
| `src/App.tsx` | Layout principal |
| `src/game/GameCanvas.tsx` | Composant Pixi.js |
| `src/game/renderer.ts` | Logique de rendu (tilemap, sprites, anims) |
| `src/game/sprites/` | Assets pixel art |
| `src/ui/HUD.tsx` | Overlay : micro, score, statut agent |
| `src/ui/MicPrompt.tsx` | Écran d'activation initial |
| `src/net/ws.ts` | Client WebSocket typé |
| `src/audio/recorder.ts` | Capture micro → PCM 16 kHz |
| `vite.config.ts`, `tsconfig.json` | Config |

## Protocole WebSocket

### Client → Serveur

```ts
{ type: "audio_chunk", data: ArrayBuffer }       // PCM 16kHz mono
{ type: "action", action: "forward"|"left"|"right"|"grab" }
{ type: "reset" }
```

### Serveur → Client

```ts
{
  type: "state",
  robot: { x, y, dir },                          // dir: 0=N, 1=E, 2=S, 3=O
  objects: [{ id, type, x, y, collected }],
  landmarks: [{ type, x, y }],
  collected: { "clé": 2, "gemme": 1, ... },
  agent: { active, status, target }
}

{ type: "voice", text: "récupère les clés", recognized_command: "AGENT clé" }
{ type: "error", message: "..." }
```

## Boucles principales

**Backend (par client connecté)** :
1. WS ouvert → init `RobotEnv` + `RobotAgent` isolés
2. Buffer audio → détection silence (~2-3s) → Whisper
3. Whisper → `commands.parse(text)` → action ou mission agent
4. `env.step()` → broadcast `state`
5. Tick agent IA toutes les ~100 ms si actif

**Frontend** :
1. WS ouvert → `MicPrompt` → demande accès micro
2. `MediaRecorder` / `AudioWorklet` → PCM 16 kHz → chunks WS
3. Réception `state` → mise à jour store → Pixi delta render
4. Clavier (↑ ← → Espace) → envoi `action`

## Rendu pixel art

**Tileset** : grille 11×11, tuile = 32 px (rendu @2x = 64 px display)

**Sprites** :
- Robot : 4 directions × 2 frames (8 sprites)
- Objets : clé, gemme, étoile, pièce, batterie + halo animé
- Repères : fontaine, statue, banc, lampadaire, panneau
- Sol : 2-3 variantes de tuile herbe
- Particules : burst au ramassage

**Source assets** : Kenney.nl (CC0) ou Pixi.Graphics programmatique en fallback.

**Couches Pixi (Container)** :
1. Background (sol, render-once)
2. Landmarks (statique)
3. Objects (halo pulsant)
4. Robot (anims, rotation tween)
5. Particles (effets ponctuels)
6. Overlay HUD React (au-dessus du canvas)

**Animations** :
- Robot : interpolation linéaire entre cellules (~150 ms)
- Rotation : tween 100 ms
- Objets : pulse vertical sin(t) + scintillement
- Ramassage : particles burst + fade-out
- Agent actif : surbrillance jaune autour du robot

**HUD React** :
- Haut-gauche : indicateur micro pulsant
- Haut-droite : score (icônes + nombres)
- Bas : dernière commande entendue + statut agent
- Coin : bouton reset, toggle son

## Gestion d'erreurs

- **WS déconnecté** : reconnect auto avec backoff (1s → 5s), bannière "Reconnexion…"
- **Permission micro refusée** : écran d'erreur avec instructions OS
- **Whisper hallucination** : ignore transcriptions < 2 caractères
- **Audio chunk corrompu** : try/except backend, drop le chunk
- **Multi-clients** : chaque WS = instance d'env isolée
- **Onglet fermé** : backend détecte déconnexion → cleanup

## Tests

- **Backend** : pytest sur `commands.parse()`, `RobotEnv.step()`, Whisper mocké
- **Frontend** : vitest sur client WS (mock socket), composants HUD avec React Testing Library
- **E2E** : reporté (complexité audio)

## Nettoyage

Suppression des fichiers Pygame actuels :
- `main.py`, `robot_env.py`, `agent.py`, `objects.py`, `requirements.txt` (racine)

Le `.venv/` reste pour le dev backend.

## Structure finale

```
command_voice_robot/
├── backend/
│   ├── main.py
│   ├── game/{env,agent,objects}.py
│   ├── voice/{recognizer,commands}.py
│   ├── protocol.py
│   ├── tests/
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── main.tsx, App.tsx
│   │   ├── game/{GameCanvas.tsx, renderer.ts, sprites/}
│   │   ├── ui/{HUD.tsx, MicPrompt.tsx}
│   │   ├── net/ws.ts
│   │   └── audio/recorder.ts
│   ├── public/sprites/
│   ├── package.json
│   ├── tsconfig.json
│   └── vite.config.ts
├── docs/superpowers/specs/
├── README.md
└── LICENSE
```

## Hors scope

- Multijoueur / synchronisation entre clients
- Sauvegarde des parties
- Mobile / touch controls
- Niveaux multiples
- Sound effects / musique
