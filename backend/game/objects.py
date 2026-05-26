"""Objets ramassables et repères du monde."""
from __future__ import annotations

import numpy as np
from dataclasses import dataclass


OBJECT_TYPES = [
    {"name": "clé",      "shape": "key"},
    {"name": "gemme",    "shape": "diamond"},
    {"name": "étoile",   "shape": "star"},
    {"name": "pièce",    "shape": "coin"},
    {"name": "batterie", "shape": "battery"},
]

LANDMARK_TYPES = [
    {"name": "fontaine",   "shape": "fountain"},
    {"name": "statue",     "shape": "statue"},
    {"name": "banc",       "shape": "bench"},
    {"name": "lampadaire", "shape": "lamp"},
    {"name": "panneau",    "shape": "sign"},
]


@dataclass
class CollectibleObject:
    obj_type: dict
    x: int
    y: int
    collected: bool = False

    @property
    def name(self) -> str:
        return self.obj_type["name"]

    @property
    def shape(self) -> str:
        return self.obj_type["shape"]

    @property
    def pos(self) -> tuple[int, int]:
        return (self.x, self.y)


@dataclass
class Landmark:
    landmark_type: dict
    x: int
    y: int

    @property
    def name(self) -> str:
        return self.landmark_type["name"]

    @property
    def shape(self) -> str:
        return self.landmark_type["shape"]

    @property
    def pos(self) -> tuple[int, int]:
        return (self.x, self.y)


def spawn_objects(grid_map: np.ndarray, grid_size: int, count: int = 6,
                  robot_pos: tuple[int, int] = (5, 5), seed: int = 123) -> list[CollectibleObject]:
    rng = np.random.RandomState(seed)
    valid = [(x, y) for x in range(grid_size) for y in range(grid_size)
             if grid_map[x, y] in (1, 2) and (x, y) != robot_pos]
    rng.shuffle(valid)
    objects = []
    for i in range(min(count, len(valid))):
        x, y = valid[i]
        objects.append(CollectibleObject(obj_type=OBJECT_TYPES[i % len(OBJECT_TYPES)], x=x, y=y))
    return objects


def spawn_landmarks(grid_map: np.ndarray, grid_size: int,
                    used: set[tuple[int, int]], seed: int = 77) -> list[Landmark]:
    rng = np.random.RandomState(seed)
    intersections = [(x, y) for x in range(grid_size) for y in range(grid_size)
                     if grid_map[x, y] == 2 and (x, y) not in used]
    rng.shuffle(intersections)
    landmarks = []
    for i, ltype in enumerate(LANDMARK_TYPES):
        if i >= len(intersections):
            break
        x, y = intersections[i]
        landmarks.append(Landmark(landmark_type=ltype, x=x, y=y))
    return landmarks
