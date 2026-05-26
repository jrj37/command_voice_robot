"""
Contrôle vocal d'un robot dans un environnement Gymnasium.
Commandes vocales : "avance", "gauche", "droite", "stop"/"quitter".
"""

from __future__ import annotations

import threading
import queue
import sys
import re
from difflib import SequenceMatcher

import speech_recognition as sr
from robot_env import RobotEnv
from agent import RobotAgent
import pygame

# ---------- Mapping parole → action ----------
# Chaque mot-clé → action (0=avancer, 1=gauche, 2=droite)
COMMANDS = {
    "avance": 0,
    "avancer": 0,
    "avant": 0,
    "avance.": 0,
    "avancé": 0,
    "avons": 0,
    "forward": 0,
    "continue": 0,
    "va": 0,
    "gauche": 1,
    "à gauche": 1,
    "agauche": 1,
    "goche": 1,
    "left": 1,
    "tourne à gauche": 1,
    "droite": 2,
    "à droite": 2,
    "adroite": 2,
    "right": 2,
    "tourne à droite": 2,
    "ramasse": 3,
    "ramasser": 3,
    "attrape": 3,
    "attraper": 3,
    "prends": 3,
    "prendre": 3,
    "grab": 3,
    "pick": 3,
    "récupère": 3,
    "recupere": 3,
    "chope": 3,
    "pince": 3,
}

STOP_WORDS = {"stop", "arrête", "arrete", "quitter", "quit", "exit"}

# Mots-clés qui déclenchent l'agent IA (format: mot-clé objet → type)
AGENT_TRIGGERS = {
    "clé": "clé",
    "cles": "clé",
    "clés": "clé",
    "clef": "clé",
    "clefs": "clé",
    "key": "clé",
    "gemme": "gemme",
    "gemmes": "gemme",
    "diamant": "gemme",
    "étoile": "étoile",
    "etoile": "étoile",
    "étoiles": "étoile",
    "etoiles": "étoile",
    "pièce": "pièce",
    "piece": "pièce",
    "pièces": "pièce",
    "pieces": "pièce",
    "batterie": "batterie",
    "batteries": "batterie",
    "tout": "all",
    "tous": "all",
    "toutes": "all",
    "everything": "all",
}

AGENT_ACTIVATE_WORDS = {
    "récupère", "recupere", "récupérer", "recuperer",
    "cherche", "chercher", "trouve", "trouver",
    "va chercher", "ramasse", "collecte", "collecter",
    "prends", "go", "fetch",
}

# Repères pour les indices vocaux
HINT_LANDMARKS = {
    "fontaine": "fontaine",
    "statue": "statue",
    "banc": "banc",
    "lampadaire": "lampadaire",
    "panneau": "panneau",
    "lampe": "lampadaire",
    "panneau de signalisation": "panneau",
    "signe": "panneau",
    "bench": "banc",
    "fountain": "fontaine",
}

HINT_WORDS = {"près", "pres", "proche", "à côté", "a cote", "vers", "côté", "cote",
              "autour", "devant", "derrière", "derriere", "near"}


def try_agent_command(text: str) -> tuple[str, int] | None:
    """Vérifie si le texte est une commande pour l'agent IA.
    Retourne (type_objet, quantité) ou None. quantité=0 signifie 'toutes'."""
    # Vérifier qu'il y a un mot d'activation
    has_trigger = any(w in text for w in AGENT_ACTIVATE_WORDS)
    if not has_trigger:
        return None
    # Chercher le type d'objet
    obj_type = None
    for keyword, otype in AGENT_TRIGGERS.items():
        if keyword in text:
            obj_type = otype
            break
    if obj_type is None:
        return None
    # Extraire un nombre (ex: "1 clé", "deux gemmes", "3 pièces")
    count = 0  # 0 = toutes
    # Nombre en chiffres
    numbers = re.findall(r'\d+', text)
    if numbers:
        count = int(numbers[0])
    # Nombre en lettres
    word_numbers = {
        "un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4,
        "cinq": 5, "six": 6, "sept": 7, "huit": 8, "neuf": 9, "dix": 10,
    }
    for word, val in word_numbers.items():
        if word in text.split():
            count = val
            break
    return (obj_type, count)


def try_hint_command(text: str) -> str | None:
    """Vérifie si le texte est un indice (ex: 'l'étoile est près de la fontaine').
    Retourne le nom du repère ou None."""
    # Faut au moins un mot d'indice
    has_hint_word = any(w in text for w in HINT_WORDS)
    if not has_hint_word:
        return None
    # Chercher le repère mentionné (plus long d'abord)
    sorted_landmarks = sorted(HINT_LANDMARKS.keys(), key=len, reverse=True)
    for keyword in sorted_landmarks:
        if keyword in text:
            return HINT_LANDMARKS[keyword]
    return None


def fuzzy_match_command(text: str) -> int | None:
    """Essaie de matcher le texte avec une commande, même approximativement."""
    text = re.sub(r"[^\w\sàâéèêëïîôùûüç]", "", text).strip()
    if not text or len(text) < 2:
        return None

    # Match exact : expressions multi-mots d'abord (les plus longues en premier)
    sorted_keywords = sorted(COMMANDS.keys(), key=len, reverse=True)
    for keyword in sorted_keywords:
        if keyword in text:
            return COMMANDS[keyword]

    # Match flou : chaque mot du texte vs chaque mot-clé
    words = text.split()
    best_score = 0.0
    best_action = None
    for word in words:
        if len(word) < 2:
            continue
        for keyword, action in COMMANDS.items():
            score = SequenceMatcher(None, word, keyword).ratio()
            if score > best_score:
                best_score = score
                best_action = action
    if best_score >= 0.6:
        return best_action
    return None


def listen_loop(cmd_queue: queue.Queue, stop_event: threading.Event, env: RobotEnv):
    """Thread qui écoute le micro en continu et pousse les commandes dans la queue."""
    try:
        recognizer = sr.Recognizer()
        recognizer.dynamic_energy_threshold = True
        recognizer.pause_threshold = 0.5

        mic = sr.Microphone()
        print("🎤 Calibration du micro (2 s) — ne parlez pas...")
        with mic as source:
            recognizer.adjust_for_ambient_noise(source, duration=2)
        print(f"   Seuil d'énergie détecté : {recognizer.energy_threshold:.0f}")
        print("✅ Micro activé ! Parlez : avance / gauche / droite / stop")
        env.set_mic_active(True)

        while not stop_event.is_set():
            try:
                with mic as source:
                    print("   👂 Écoute...", flush=True)
                    audio = recognizer.listen(source, timeout=8, phrase_time_limit=3)
                print("   📡 Reconnaissance Whisper...", flush=True)
                text = recognizer.recognize_whisper(
                    audio, model="small", language="french"
                ).lower().strip()
                # Nettoyer la ponctuation et les espaces
                text = re.sub(r"[^\w\sàâéèêëïîôùûüç]", "", text).strip()
                print(f"   🗣️  Entendu : \"{text}\"")

                # Ignorer les résultats vides ou trop courts (hallucinations)
                if len(text) < 2:
                    print("   ⏳ (silence détecté)")
                    continue

                env.set_last_command(text)

                if any(w in text for w in STOP_WORDS):
                    cmd_queue.put("STOP")
                    stop_event.set()
                    break

                # Vérifier si c'est un indice pour l'agent
                hint_landmark = try_hint_command(text)
                if hint_landmark is not None:
                    cmd_queue.put(("HINT", hint_landmark))
                    print(f"   💡 Indice détecté : près de {hint_landmark}")
                    continue

                # Vérifier si c'est une commande agent IA
                agent_target = try_agent_command(text)
                if agent_target is not None:
                    cmd_queue.put(("AGENT", agent_target[0], agent_target[1]))
                    label = f"{agent_target[1]} {agent_target[0]}" if agent_target[1] > 0 else f"toutes les {agent_target[0]}s"
                    print(f"   🤖 Agent IA demandé : {label}")
                    continue

                action = fuzzy_match_command(text)
                if action is not None:
                    cmd_queue.put(action)
                    print(f"   ✅ Action : {['avancer','gauche','droite','ramasser'][action]}")
                else:
                    print(f"   ⚠️  Commande non reconnue : \"{text}\"")

            except sr.WaitTimeoutError:
                print("   ⏳ Pas de son détecté, j'écoute toujours...", flush=True)
            except sr.UnknownValueError:
                print("   ❓ Parole non comprise, réessayez.")
            except sr.RequestError as e:
                print(f"   ❌ Erreur API reconnaissance vocale : {e}")
                print("   💡 Vérifiez votre connexion internet.")
    except Exception as e:
        print(f"   ❌ Erreur micro : {e}")
        print("   💡 Sur macOS : Préférences Système > Sécurité > Microphone > autoriser Terminal")
        env.set_mic_active(False)


def show_mic_prompt(screen, font_lg, font_md):
    """Affiche un écran demandant d'activer le micro. Retourne True si l'user accepte."""
    clock = pygame.time.Clock()
    blink = True
    frame = 0

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN or event.key == pygame.K_SPACE:
                    return True
                if event.key == pygame.K_ESCAPE:
                    return False

        w, h = screen.get_size()
        screen.fill((18, 18, 28))

        # Cercle décoratif pulsant
        frame += 1
        pulse = 4 * abs((frame % 60) - 30) / 30
        radius = int(50 + pulse * 8)
        mic_circle_surf = pygame.Surface((radius * 2 + 20, radius * 2 + 20), pygame.SRCALPHA)
        pygame.draw.circle(mic_circle_surf, (80, 200, 255, 40), (radius + 10, radius + 10), radius)
        pygame.draw.circle(mic_circle_surf, (80, 200, 255, 80), (radius + 10, radius + 10), radius - 15)
        screen.blit(mic_circle_surf, (w // 2 - radius - 10, h // 2 - 120 - radius - 10))

        # Icone micro (texte)
        mic_txt = font_lg.render("🎤", True, (80, 200, 255))
        screen.blit(mic_txt, (w // 2 - mic_txt.get_width() // 2, h // 2 - 130))

        # Titre
        title = font_lg.render("Activation du Microphone", True, (220, 220, 220))
        screen.blit(title, (w // 2 - title.get_width() // 2, h // 2 - 50))

        # Description
        desc_lines = [
            "Ce robot se controle avec votre voix.",
            "Commandes : avance, gauche, droite, ramasse, stop",
            "",
            "Votre micro va etre utilise pour la",
            "reconnaissance vocale (Whisper, local).",
        ]
        for i, line in enumerate(desc_lines):
            txt = font_md.render(line, True, (150, 150, 170))
            screen.blit(txt, (w // 2 - txt.get_width() // 2, h // 2 + 10 + i * 24))

        # Bouton clignotant
        blink = (frame // 30) % 2 == 0
        btn_col = (80, 200, 255) if blink else (60, 160, 210)
        btn_text = font_lg.render("[  ESPACE  ]  Activer le micro", True, btn_col)
        screen.blit(btn_text, (w // 2 - btn_text.get_width() // 2, h // 2 + 160))

        esc_text = font_md.render("Echap pour quitter", True, (80, 80, 100))
        screen.blit(esc_text, (w // 2 - esc_text.get_width() // 2, h // 2 + 210))

        pygame.display.flip()
        clock.tick(30)


def main():
    # Init pygame d'abord pour l'écran de prompt
    pygame.init()

    grid_size = 11
    cell_size = 64
    ws = grid_size * cell_size
    hud_h = 64
    screen = pygame.display.set_mode((ws, ws + hud_h))
    pygame.display.set_caption("Robot Voice Control")

    font_lg = pygame.font.SysFont("Menlo", 20, bold=True)
    font_md = pygame.font.SysFont("Menlo", 14)

    # ── Écran d'activation micro ──
    if not show_mic_prompt(screen, font_lg, font_md):
        pygame.quit()
        print("👋 Annulé.")
        sys.exit(0)

    # Créer l'environnement (réutilise la fenêtre pygame déjà ouverte)
    env = RobotEnv(render_mode="human", grid_size=grid_size)
    env.window = screen
    env.clock = pygame.time.Clock()
    env.font_sm = pygame.font.SysFont("Menlo", 13)
    env.font_md = pygame.font.SysFont("Menlo", 15, bold=True)
    env.font_lg = pygame.font.SysFont("Menlo", 20, bold=True)
    env.reset()

    # Queue de commandes
    cmd_queue: queue.Queue = queue.Queue()
    stop_event = threading.Event()

    # Lancer l'écoute vocale
    listener = threading.Thread(target=listen_loop, args=(cmd_queue, stop_event, env), daemon=True)
    listener.start()

    print("\n🤖 Robot prêt ! Commandes vocales :")
    print("   • \"avance\"  → le robot avance")
    print("   • \"gauche\"  → tourne à gauche")
    print("   • \"droite\"  → tourne à droite")
    print("   • \"ramasse\" → attrape un objet proche")
    print("   • \"cherche les clés\" → agent IA collecte auto")
    print("   • \"près de la fontaine\" → indice pour l'agent")
    print("   • \"stop\"    → quitter")
    print("   🎮 Clavier : ↑ ← → Espace(ramasser) A(agent clés) Esc\n")

    # Agent IA
    agent = RobotAgent()
    agent_tick_delay = 0  # compteur pour ralentir l'agent (animation fluide)
    AGENT_SPEED = 4       # nombre de frames entre chaque action agent

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                break
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP:
                    agent.cancel_with_env(env)
                    env.step(0)
                elif event.key == pygame.K_LEFT:
                    agent.cancel_with_env(env)
                    env.step(1)
                elif event.key == pygame.K_RIGHT:
                    agent.cancel_with_env(env)
                    env.step(2)
                elif event.key == pygame.K_SPACE:
                    env.step(3)
                elif event.key == pygame.K_a:
                    # Raccourci clavier pour lancer l'agent sur les clés
                    agent.start_mission(env, "clé")
                elif event.key == pygame.K_ESCAPE:
                    running = False

        while not cmd_queue.empty():
            cmd = cmd_queue.get_nowait()
            if cmd == "STOP":
                running = False
                break
            if isinstance(cmd, tuple) and cmd[0] == "AGENT":
                agent.start_mission(env, cmd[1], max_collect=cmd[2])
                continue
            if isinstance(cmd, tuple) and cmd[0] == "HINT":
                if agent.active:
                    agent.give_hint(env, cmd[1])
                else:
                    env.set_last_command(f"Indice ignoré (agent inactif)")
                continue
            # Une commande manuelle annule l'agent
            if agent.active:
                agent.cancel_with_env(env)
            env.step(cmd)

        # Tick de l'agent IA (ralenti pour voir les mouvements)
        if agent.active:
            agent_tick_delay += 1
            if agent_tick_delay >= AGENT_SPEED:
                agent_tick_delay = 0
                action = agent.tick(env)
                if action is not None:
                    env.step(action)
            # Afficher le statut de l'agent dans le HUD
            env.set_last_command(f"🤖 {agent.status_message}")

        # Toujours rafraîchir l'affichage (pour le HUD micro, etc.)
        env.render()
        pygame.time.wait(50)

    stop_event.set()
    env.close()
    print("👋 Au revoir !")
    sys.exit(0)


if __name__ == "__main__":
    main()
