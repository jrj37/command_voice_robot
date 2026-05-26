"""Environnement headless : logique de jeu pure (sans rendu)."""
from __future__ import annotations

import numpy as np

from .objects import CollectibleObject, Landmark, spawn_objects, spawn_landmarks


DIRECTION_DELTAS = {
    0: (0, -1),   # Nord
    1: (1, 0),    # Est
    2: (0, 1),    # Sud
    3: (-1, 0),   # Ouest
}
DIRECTION_NAMES = {0: "Nord", 1: "Est", 2: "Sud", 3: "Ouest"}

ROAD_COLS = {2, 5, 8}
ROAD_ROWS = {2, 5, 8}


class RobotEnv:
    """Robot sur grille 11×11 : routes, trottoirs, herbe, bâtiments."""

    def __init__(self, grid_size: int = 11):
        self.grid_size = grid_size
        self._map = self._generate_map()
        self._rng = np.random.RandomState(42)
        self._decorations = self._generate_decorations()
        self.fog_visited: set[tuple[int, int]] | None = None
        self.reset()

    def reset(self):
        self.position = [5, 5]
        self.orientation = 0
        self.trail: list[tuple[int, int]] = []
        self.last_command = ""
        self.inventory: list[CollectibleObject] = []
        self.objects = spawn_objects(self._map, self.grid_size)
        used = {o.pos for o in self.objects}
        self.landmarks = spawn_landmarks(self._map, self.grid_size, used)
        self.fog_visited = None
        self.last_grab_event: dict | None = None

    def _generate_map(self):
        """0=herbe, 1=route, 2=trottoir, 3=bâtiment"""
        grid = np.zeros((self.grid_size, self.grid_size), dtype=np.int8)
        for x in range(self.grid_size):
            for y in range(self.grid_size):
                if x in ROAD_COLS or y in ROAD_ROWS:
                    grid[x, y] = 1
                    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < self.grid_size and 0 <= ny < self.grid_size:
                            if grid[nx, ny] == 0:
                                grid[nx, ny] = 2
        for x in range(self.grid_size):
            for y in range(self.grid_size):
                if grid[x, y] == 0:
                    grid[x, y] = 3
        return grid

    def _generate_decorations(self):
        decos = {}
        for x in range(self.grid_size):
            for y in range(self.grid_size):
                if self._map[x, y] == 3:
                    decos[(x, y)] = {
                        "type": str(self._rng.choice(["building", "tree", "tree"])),
                        "color_idx": int(self._rng.randint(0, 3)),
                        "height": float(self._rng.uniform(0.5, 0.9)),
                        "windows": int(self._rng.randint(1, 5)),
                    }
                elif self._map[x, y] == 2:
                    if self._rng.random() < 0.2:
                        decos[(x, y)] = {"type": "small_tree"}
        return decos

    def step(self, action: int):
        old_pos = list(self.position)
        self.last_grab_event = None

        if action == 0:
            dx, dy = DIRECTION_DELTAS[self.orientation]
            nx = max(0, min(self.grid_size - 1, self.position[0] + dx))
            ny = max(0, min(self.grid_size - 1, self.position[1] + dy))
            self.position = [nx, ny]
        elif action == 1:
            self.orientation = (self.orientation - 1) % 4
        elif action == 2:
            self.orientation = (self.orientation + 1) % 4
        elif action == 3:
            self._try_grab()

        if old_pos != self.position:
            self.trail.append((old_pos[0], old_pos[1]))
            if len(self.trail) > 50:
                self.trail.pop(0)

    def _try_grab(self):
        dx, dy = DIRECTION_DELTAS[self.orientation]
        front = (
            max(0, min(self.grid_size - 1, self.position[0] + dx)),
            max(0, min(self.grid_size - 1, self.position[1] + dy)),
        )
        check = [tuple(self.position), front]
        for obj in self.objects:
            if obj.collected:
                continue
            if obj.pos in check:
                obj.collected = True
                self.inventory.append(obj)
                self.last_grab_event = {"success": True, "name": obj.name, "x": obj.x, "y": obj.y}
                return
        self.last_grab_event = {"success": False}

    def get_nearby_objects(self) -> list[CollectibleObject]:
        nearby = []
        for obj in self.objects:
            if obj.collected:
                continue
            if abs(obj.x - self.position[0]) + abs(obj.y - self.position[1]) <= 1:
                nearby.append(obj)
        return nearby

    @property
    def map_array(self) -> np.ndarray:
        return self._map

    def serialize_static(self) -> dict:
        """Tout ce qui ne change jamais : map + déco + landmarks."""
        return {
            "grid_size": self.grid_size,
            "map": self._map.tolist(),
            "decorations": [
                {"x": x, "y": y, **d} for (x, y), d in self._decorations.items()
            ],
            "landmarks": [
                {"name": lm.name, "shape": lm.shape, "x": lm.x, "y": lm.y}
                for lm in self.landmarks
            ],
        }

    def serialize_state(self) -> dict:
        """Ce qui change à chaque step."""
        inventory_counts: dict[str, int] = {}
        for o in self.inventory:
            inventory_counts[o.name] = inventory_counts.get(o.name, 0) + 1
        return {
            "robot": {
                "x": self.position[0],
                "y": self.position[1],
                "dir": self.orientation,
                "dir_name": DIRECTION_NAMES[self.orientation],
            },
            "objects": [
                {"id": i, "type": o.name, "shape": o.shape,
                 "x": o.x, "y": o.y, "collected": o.collected}
                for i, o in enumerate(self.objects)
            ],
            "trail": [list(t) for t in self.trail],
            "inventory": inventory_counts,
            "inventory_total": len(self.inventory),
            "objects_total": len(self.objects),
            "fog_visited": [list(c) for c in self.fog_visited] if self.fog_visited else None,
            "grab_event": self.last_grab_event,
            "nearby": [o.name for o in self.get_nearby_objects()],
        }
