# 🤖 Command Voice Robot

Contrôle vocal d'un robot dans un environnement de grille 2D (Gymnasium + Pygame), avec reconnaissance vocale locale via **Whisper** et un **agent IA** capable de collecter des objets de manière autonome.

## ✨ Fonctionnalités

- 🎤 **Reconnaissance vocale en français** (Whisper, local, sans clé API)
- 🕹️ **Contrôle manuel** du robot à la voix ou au clavier
- 🤖 **Agent IA autonome** : demande au robot d'aller chercher des objets ("récupère les clés", "ramasse 3 gemmes")
- 💡 **Indices vocaux** : aide l'agent en lui donnant des repères ("près de la fontaine")
- 🎨 **Interface Pygame** avec HUD, animations et écran d'activation du micro
- 🔍 **Matching flou** des commandes : tolère les variations et erreurs de reconnaissance

## 🗣️ Commandes vocales

| Commande | Action |
|----------|--------|
| `avance`, `avancer`, `forward` | Le robot avance |
| `gauche`, `à gauche`, `left` | Tourne à gauche |
| `droite`, `à droite`, `right` | Tourne à droite |
| `ramasse`, `attrape`, `prends` | Attrape un objet proche |
| `cherche les clés`, `récupère 3 gemmes` | Lance l'agent IA |
| `près de la fontaine` | Donne un indice à l'agent |
| `stop`, `quitter`, `exit` | Quitter |

### Objets reconnus par l'agent IA
`clé`, `gemme`, `étoile`, `pièce`, `batterie` — ou `tout` pour collecter l'ensemble.

### Repères pour les indices
`fontaine`, `statue`, `banc`, `lampadaire`, `panneau`.

## ⌨️ Raccourcis clavier

| Touche | Action |
|--------|--------|
| `↑` | Avancer |
| `←` | Tourner à gauche |
| `→` | Tourner à droite |
| `Espace` | Ramasser |
| `A` | Lancer l'agent IA sur les clés |
| `Échap` | Quitter |

## 📦 Installation

### Prérequis
- Python 3.9+
- Un microphone
- macOS / Linux / Windows
- Autorisation micro pour le terminal (sur macOS : *Préférences Système → Sécurité → Microphone*)

### Étapes

```bash
# Cloner le repo
git clone https://github.com/jrj37/command_voice_robot.git
cd command_voice_robot

# Créer un environnement virtuel
python3 -m venv .venv
source .venv/bin/activate   # sur Windows : .venv\Scripts\activate

# Installer les dépendances
pip install -r requirements.txt
```

> ⚠️ **PyAudio** peut nécessiter des dépendances système :
> - macOS : `brew install portaudio`
> - Linux : `sudo apt install portaudio19-dev python3-pyaudio`

## 🚀 Lancement

```bash
python main.py
```

1. Une fenêtre s'ouvre avec un écran d'activation du micro.
2. Appuyez sur `Espace` pour activer.
3. Parlez ou utilisez le clavier.

## 🏗️ Architecture

| Fichier | Rôle |
|---------|------|
| `main.py` | Boucle principale, reconnaissance vocale, gestion des événements |
| `robot_env.py` | Environnement Gymnasium personnalisé + rendu Pygame |
| `agent.py` | Agent IA autonome (pathfinding, collecte d'objets) |
| `objects.py` | Définition des objets du monde (clés, gemmes, repères, etc.) |
| `requirements.txt` | Dépendances Python |

## 🧠 Comment ça marche

1. Un **thread d'écoute** capture l'audio en continu via `SpeechRecognition`.
2. **Whisper** (modèle `small`, local) transcrit l'audio en texte français.
3. Le texte est analysé : commande manuelle ? mission agent ? indice ?
4. Les commandes sont poussées dans une **queue thread-safe** consommée par la boucle principale.
5. Le **matching flou** (`difflib.SequenceMatcher`) rattrape les erreurs de reconnaissance.
6. L'**agent IA** planifie un chemin vers la cible et exécute les actions une par une.

## 📜 Licence

Projet personnel — libre d'utilisation.
