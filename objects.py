"""
Objets ramassables pour le robot.
Chaque objet a un type, une position, une couleur et un symbole.
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass, field


# ─── Types d'objets ─────────────────────────────────────────
OBJECT_TYPES = [
    {"name": "clé",      "symbol": "🔑", "color": (255, 215, 0),   "shape": "key"},
    {"name": "gemme",    "symbol": "💎", "color": (0, 200, 255),   "shape": "diamond"},
    {"name": "étoile",   "symbol": "⭐", "color": (255, 255, 80),  "shape": "star"},
    {"name": "pièce",    "symbol": "🪙", "color": (220, 180, 50),  "shape": "coin"},
    {"name": "batterie", "symbol": "🔋", "color": (80, 220, 80),   "shape": "battery"},
]

# ─── Types de repères ───────────────────────────────────────
LANDMARK_TYPES = [
    {"name": "fontaine",   "color": (100, 180, 255), "shape": "fountain"},
    {"name": "statue",     "color": (180, 160, 140), "shape": "statue"},
    {"name": "banc",       "color": (160, 120, 80),  "shape": "bench"},
    {"name": "lampadaire", "color": (240, 220, 100), "shape": "lamp"},
    {"name": "panneau",    "color": (220, 80, 80),   "shape": "sign"},
]


@dataclass
class CollectibleObject:
    """Un objet ramassable sur la carte."""
    obj_type: dict
    x: int
    y: int
    collected: bool = False
    # Animation de flottement
    anim_offset: float = 0.0

    @property
    def name(self) -> str:
        return self.obj_type["name"]

    @property
    def color(self) -> tuple:
        return self.obj_type["color"]

    @property
    def shape(self) -> str:
        return self.obj_type["shape"]

    @property
    def pos(self) -> tuple[int, int]:
        return (self.x, self.y)


@dataclass
class Landmark:
    """Un repère identifiable sur la carte."""
    landmark_type: dict
    x: int
    y: int

    @property
    def name(self) -> str:
        return self.landmark_type["name"]

    @property
    def color(self) -> tuple:
        return self.landmark_type["color"]

    @property
    def shape(self) -> str:
        return self.landmark_type["shape"]

    @property
    def pos(self) -> tuple[int, int]:
        return (self.x, self.y)


def spawn_objects(grid_map: np.ndarray, grid_size: int, count: int = 6,
                  robot_pos: tuple[int, int] = (5, 5), seed: int = 123) -> list[CollectibleObject]:
    """Place des objets sur les routes et trottoirs (pas sur bâtiments/arbres)."""
    rng = np.random.RandomState(seed)
    valid_cells = []
    for x in range(grid_size):
        for y in range(grid_size):
            # Routes (1) et trottoirs (2) sont accessibles
            if grid_map[x, y] in (1, 2) and (x, y) != robot_pos:
                valid_cells.append((x, y))

    rng.shuffle(valid_cells)
    objects = []
    used = set()
    for i in range(min(count, len(valid_cells))):
        pos = valid_cells[i]
        if pos in used:
            continue
        used.add(pos)
        obj_type = OBJECT_TYPES[i % len(OBJECT_TYPES)]
        obj = CollectibleObject(
            obj_type=obj_type,
            x=pos[0], y=pos[1],
            anim_offset=rng.uniform(0, 2 * np.pi),
        )
        objects.append(obj)
    return objects


def spawn_landmarks(grid_map: np.ndarray, grid_size: int,
                    used_positions: set[tuple[int, int]],
                    seed: int = 77) -> list[Landmark]:
    """Place des repères sur les intersections et trottoirs."""
    rng = np.random.RandomState(seed)

    # Intersections : croisements de routes
    intersections = []
    for x in range(grid_size):
        for y in range(grid_size):
            if grid_map[x, y] == 2 and (x, y) not in used_positions:
                intersections.append((x, y))

    rng.shuffle(intersections)
    landmarks = []
    used = set(used_positions)

    for i, ltype in enumerate(LANDMARK_TYPES):
        if i >= len(intersections):
            break
        pos = intersections[i]
        if pos in used:
            continue
        used.add(pos)
        landmarks.append(Landmark(landmark_type=ltype, x=pos[0], y=pos[1]))

    return landmarks
