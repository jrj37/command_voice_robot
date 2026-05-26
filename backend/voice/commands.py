"""Parser texte → commande de jeu."""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from dataclasses import dataclass


COMMANDS = {
    "avance": 0, "avancer": 0, "avant": 0, "avancé": 0, "forward": 0,
    "continue": 0, "va": 0,
    "gauche": 1, "à gauche": 1, "agauche": 1, "goche": 1, "left": 1, "tourne à gauche": 1,
    "droite": 2, "à droite": 2, "adroite": 2, "right": 2, "tourne à droite": 2,
    "ramasse": 3, "ramasser": 3, "attrape": 3, "attraper": 3, "prends": 3,
    "prendre": 3, "grab": 3, "pick": 3, "chope": 3, "pince": 3,
}

STOP_WORDS = {"stop", "arrête", "arrete", "quitter", "quit", "exit"}

AGENT_TRIGGERS = {
    "clé": "clé", "cles": "clé", "clés": "clé", "clef": "clé", "clefs": "clé", "key": "clé",
    "gemme": "gemme", "gemmes": "gemme", "diamant": "gemme",
    "étoile": "étoile", "etoile": "étoile", "étoiles": "étoile", "etoiles": "étoile",
    "pièce": "pièce", "piece": "pièce", "pièces": "pièce", "pieces": "pièce",
    "batterie": "batterie", "batteries": "batterie",
    "tout": "all", "tous": "all", "toutes": "all", "everything": "all",
}

AGENT_ACTIVATE_WORDS = {
    "récupère", "recupere", "récupérer", "recuperer",
    "cherche", "chercher", "trouve", "trouver",
    "ramasse", "collecte", "collecter",
    "prends", "go", "fetch",
}

HINT_LANDMARKS = {
    "fontaine": "fontaine", "statue": "statue", "banc": "banc",
    "lampadaire": "lampadaire", "panneau": "panneau", "lampe": "lampadaire",
    "panneau de signalisation": "panneau", "signe": "panneau",
    "bench": "banc", "fountain": "fontaine",
}

HINT_WORDS = {"près", "pres", "proche", "à côté", "a cote", "vers", "côté", "cote",
              "autour", "devant", "derrière", "derriere", "near"}

WORD_NUMBERS = {
    "un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5,
    "six": 6, "sept": 7, "huit": 8, "neuf": 9, "dix": 10,
}


@dataclass
class ParsedCommand:
    kind: str  # "action" | "agent" | "hint" | "stop" | "unknown"
    action: int | None = None
    target_type: str | None = None
    count: int = 0
    landmark: str | None = None


def normalize(text: str) -> str:
    text = text.lower().strip()
    return re.sub(r"[^\w\sàâéèêëïîôùûüç]", "", text).strip()


def try_agent_command(text: str) -> tuple[str, int] | None:
    if not any(w in text for w in AGENT_ACTIVATE_WORDS):
        return None
    obj_type = None
    for keyword, otype in AGENT_TRIGGERS.items():
        if keyword in text:
            obj_type = otype
            break
    if obj_type is None:
        return None
    count = 0
    numbers = re.findall(r"\d+", text)
    if numbers:
        count = int(numbers[0])
    for word, val in WORD_NUMBERS.items():
        if word in text.split():
            count = val
            break
    return (obj_type, count)


def try_hint_command(text: str) -> str | None:
    if not any(w in text for w in HINT_WORDS):
        return None
    for keyword in sorted(HINT_LANDMARKS.keys(), key=len, reverse=True):
        if keyword in text:
            return HINT_LANDMARKS[keyword]
    return None


def fuzzy_match_command(text: str) -> int | None:
    text = normalize(text)
    if not text or len(text) < 2:
        return None
    for keyword in sorted(COMMANDS.keys(), key=len, reverse=True):
        if keyword in text:
            return COMMANDS[keyword]
    best_score, best_action = 0.0, None
    for word in text.split():
        if len(word) < 2:
            continue
        for keyword, action in COMMANDS.items():
            score = SequenceMatcher(None, word, keyword).ratio()
            if score > best_score:
                best_score, best_action = score, action
    return best_action if best_score >= 0.6 else None


def parse(text: str) -> ParsedCommand:
    text = normalize(text)
    if not text or len(text) < 2:
        return ParsedCommand(kind="unknown")
    if any(w in text for w in STOP_WORDS):
        return ParsedCommand(kind="stop")
    hint = try_hint_command(text)
    if hint is not None:
        return ParsedCommand(kind="hint", landmark=hint)
    agent = try_agent_command(text)
    if agent is not None:
        return ParsedCommand(kind="agent", target_type=agent[0], count=agent[1])
    action = fuzzy_match_command(text)
    if action is not None:
        return ParsedCommand(kind="action", action=action)
    return ParsedCommand(kind="unknown")
