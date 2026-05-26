"""Agent IA autonome — exploration + collecte avec champ de vision limité."""
from __future__ import annotations

from collections import deque
import numpy as np


DIRECTION_DELTAS = {0: (0, -1), 1: (1, 0), 2: (0, 1), 3: (-1, 0)}
VISION_RANGE = 3


def bfs_path(grid_map: np.ndarray, start: tuple[int, int],
             goal: tuple[int, int], grid_size: int) -> list[tuple[int, int]] | None:
    if start == goal:
        return [start]
    walkable = {1, 2}
    visited = {start}
    parent = {}
    queue = deque([start])
    while queue:
        cx, cy = queue.popleft()
        for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
            nx, ny = cx + dx, cy + dy
            if 0 <= nx < grid_size and 0 <= ny < grid_size:
                if (nx, ny) not in visited and grid_map[nx, ny] in walkable:
                    visited.add((nx, ny))
                    parent[(nx, ny)] = (cx, cy)
                    if (nx, ny) == goal:
                        path = [(nx, ny)]
                        while path[-1] != start:
                            path.append(parent[path[-1]])
                        path.reverse()
                        return path
                    queue.append((nx, ny))
    return None


def path_to_actions(path, start_orientation: int, grab_at_end: bool = False) -> list[int]:
    if len(path) < 2:
        return [3] if grab_at_end else []
    actions = []
    orientation = start_orientation
    for i in range(len(path) - 1):
        cx, cy = path[i]
        nx, ny = path[i + 1]
        dx, dy = nx - cx, ny - cy
        target_orientation = None
        for ori, (odx, ody) in DIRECTION_DELTAS.items():
            if (odx, ody) == (dx, dy):
                target_orientation = ori
                break
        if target_orientation is None:
            continue
        while orientation != target_orientation:
            diff = (target_orientation - orientation) % 4
            if diff == 1:
                actions.append(2); orientation = (orientation + 1) % 4
            elif diff == 3:
                actions.append(1); orientation = (orientation - 1) % 4
            elif diff == 2:
                actions.append(2); orientation = (orientation + 1) % 4
            else:
                break
        actions.append(0)
    if grab_at_end:
        actions.append(3)
    return actions


class RobotAgent:
    def __init__(self):
        self.active = False
        self.action_queue: deque[int] = deque()
        self.target_type: str = ""
        self.current_target = None
        self.status_message = ""
        self.collected_count = 0
        self.max_collect = 0
        self.visited_cells: set[tuple[int, int]] = set()
        self.discovered_objects: list = []
        self.mode = "exploring"
        self.hint_position: tuple[int, int] | None = None

    def serialize(self) -> dict:
        return {
            "active": self.active,
            "status": self.status_message,
            "target_type": self.target_type,
            "collected": self.collected_count,
            "max_collect": self.max_collect,
            "mode": self.mode,
        }

    def _scan_surroundings(self, env):
        rx, ry = env.position[0], env.position[1]
        for dx in range(-VISION_RANGE, VISION_RANGE + 1):
            for dy in range(-VISION_RANGE, VISION_RANGE + 1):
                if abs(dx) + abs(dy) <= VISION_RANGE:
                    nx, ny = rx + dx, ry + dy
                    if 0 <= nx < env.grid_size and 0 <= ny < env.grid_size:
                        self.visited_cells.add((nx, ny))
        env.fog_visited = self.visited_cells
        for obj in env.objects:
            if obj.collected or obj in self.discovered_objects:
                continue
            if abs(obj.x - rx) + abs(obj.y - ry) <= VISION_RANGE:
                self.discovered_objects.append(obj)

    def _is_target(self, obj) -> bool:
        if self.target_type == "all":
            return True
        return self.target_type in obj.name.lower()

    def start_mission(self, env, target_type: str, max_collect: int = 0):
        self.target_type = target_type
        self.active = True
        self.action_queue.clear()
        self.discovered_objects = []
        self.visited_cells = set()
        self.collected_count = 0
        self.max_collect = max_collect
        self.mode = "exploring"
        self.current_target = None
        self.hint_position = None
        label = f"{max_collect} {target_type}(s)" if max_collect > 0 else f"toutes les {target_type}s"
        self.status_message = f"Recherche : {label}..."
        self._scan_surroundings(env)
        self._decide_next(env)

    def _decide_next(self, env):
        self.discovered_objects = [o for o in self.discovered_objects if not o.collected]
        targets = [o for o in self.discovered_objects if self._is_target(o)]
        if targets:
            self.mode = "collecting"
            robot_pos = (env.position[0], env.position[1])
            best_obj, best_path, best_len = None, None, float("inf")
            for obj in targets:
                path = bfs_path(env.map_array, robot_pos, obj.pos, env.grid_size)
                if path and len(path) < best_len:
                    best_len, best_path, best_obj = len(path), path, obj
            if best_obj and best_path:
                self.current_target = best_obj
                self.action_queue = deque(path_to_actions(best_path, env.orientation, grab_at_end=True))
                self.status_message = f"→ {best_obj.name} repéré ! [{best_len - 1} pas]"
                return
        self.mode = "exploring"
        self.current_target = None
        self._plan_exploration(env)

    def give_hint(self, env, landmark_name: str) -> bool:
        for lm in env.landmarks:
            if lm.name == landmark_name:
                self.hint_position = lm.pos
                self.action_queue.clear()
                self._plan_exploration(env)
                self.status_message = f"Indice : près de {landmark_name} !"
                return True
        return False

    def _plan_exploration(self, env):
        robot_pos = (env.position[0], env.position[1])
        grid_size = env.grid_size
        walkable = {1, 2}

        if self.hint_position is not None:
            hx, hy = self.hint_position
            candidates = []
            for x in range(grid_size):
                for y in range(grid_size):
                    if (x, y) not in self.visited_cells and env.map_array[x, y] in walkable:
                        candidates.append(((x, y), abs(x - hx) + abs(y - hy)))
            candidates.sort(key=lambda c: c[1])
            if not candidates:
                self.hint_position = None
            else:
                for (tx, ty), _ in candidates:
                    path = bfs_path(env.map_array, robot_pos, (tx, ty), grid_size)
                    if path:
                        self.action_queue = deque(path_to_actions(path, env.orientation))
                        self.status_message = f"Indice : vers {self.hint_position}..."
                        return
                self.hint_position = None

        visited_bfs = {robot_pos}
        parent = {}
        queue = deque([robot_pos])
        target = None
        while queue:
            cx, cy = queue.popleft()
            if (cx, cy) not in self.visited_cells and (cx, cy) != robot_pos:
                target = (cx, cy)
                break
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < grid_size and 0 <= ny < grid_size:
                    if (nx, ny) not in visited_bfs and env.map_array[nx, ny] in walkable:
                        visited_bfs.add((nx, ny))
                        parent[(nx, ny)] = (cx, cy)
                        queue.append((nx, ny))

        if target is None:
            self.status_message = f"Carte explorée — {self.collected_count} collecté(s)"
            self.active = False
            env.fog_visited = None
            return

        path = [target]
        while path[-1] != robot_pos:
            path.append(parent[path[-1]])
        path.reverse()
        self.action_queue = deque(path_to_actions(path, env.orientation))
        self.status_message = f"Exploration... ({len(self.visited_cells)} cases vues)"

    def tick(self, env) -> int | None:
        if not self.active:
            return None
        self._scan_surroundings(env)
        if self.mode == "exploring":
            targets = [o for o in self.discovered_objects
                       if self._is_target(o) and not o.collected]
            if targets:
                self.action_queue.clear()
                self._decide_next(env)
        if not self.action_queue:
            if self.current_target and self.current_target.collected:
                self.collected_count += 1
                self.current_target = None
                if self.max_collect > 0 and self.collected_count >= self.max_collect:
                    self.status_message = f"Mission accomplie ! ({self.collected_count} collectés)"
                    self.active = False
                    env.fog_visited = None
                    return None
            self._decide_next(env)
            if not self.action_queue:
                return None
        return self.action_queue.popleft()

    def cancel(self, env):
        self.active = False
        self.action_queue.clear()
        self.discovered_objects = []
        self.current_target = None
        self.status_message = "Mission annulée"
        env.fog_visited = None
