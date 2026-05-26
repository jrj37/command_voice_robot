"""
Agent IA autonome : explore la carte à l'aveugle avec un champ de vision limité.
Le robot ne connaît PAS la position des objets. Il doit explorer pour les découvrir.
Quand il repère un objet cible dans son champ de vision, il va le récupérer.
"""

from __future__ import annotations

from collections import deque
import numpy as np


# Orientations : 0=Nord(y-1), 1=Est(x+1), 2=Sud(y+1), 3=Ouest(x-1)
DIRECTION_DELTAS = {
    0: (0, -1),
    1: (1, 0),
    2: (0, 1),
    3: (-1, 0),
}

VISION_RANGE = 3  # le robot voit à 3 cases de distance


def bfs_path(grid_map: np.ndarray, start: tuple[int, int],
             goal: tuple[int, int], grid_size: int) -> list[tuple[int, int]] | None:
    """BFS sur la grille. Ne traverse que les cases routes (1) ou trottoirs (2)."""
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


def path_to_actions(path: list[tuple[int, int]], start_orientation: int,
                    grab_at_end: bool = False) -> list[int]:
    """Convertit un chemin en séquence d'actions. Optionnellement ramasse à la fin."""
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
                actions.append(2)
                orientation = (orientation + 1) % 4
            elif diff == 3:
                actions.append(1)
                orientation = (orientation - 1) % 4
            elif diff == 2:
                actions.append(2)
                orientation = (orientation + 1) % 4
            else:
                break
        actions.append(0)

    if grab_at_end:
        actions.append(3)
    return actions


class RobotAgent:
    """Agent IA qui explore la carte à l'aveugle pour trouver et collecter des objets."""

    def __init__(self):
        self.active = False
        self.action_queue: deque[int] = deque()
        self.target_type: str = ""
        self.current_target = None
        self.status_message = ""
        self.collected_count = 0
        self.max_collect = 0  # 0 = pas de limite
        # Exploration
        self.visited_cells: set[tuple[int, int]] = set()
        self.discovered_objects: list = []  # objets repérés mais pas encore collectés
        self.mode = "exploring"  # "exploring" ou "collecting"
        # Indices (hints)
        self.hint_position: tuple[int, int] | None = None

    def _scan_surroundings(self, env):
        """Regarde autour du robot dans son champ de vision et découvre des objets.
        Marque TOUTES les cases visibles comme visitées."""
        rx, ry = int(env.position[0]), int(env.position[1])

        # Marquer toutes les cases dans le champ de vision comme vues
        for dx in range(-VISION_RANGE, VISION_RANGE + 1):
            for dy in range(-VISION_RANGE, VISION_RANGE + 1):
                if abs(dx) + abs(dy) <= VISION_RANGE:
                    nx, ny = rx + dx, ry + dy
                    if 0 <= nx < env.grid_size and 0 <= ny < env.grid_size:
                        self.visited_cells.add((nx, ny))

        # Synchroniser avec l'environnement pour l'affichage
        env.fog_visited = self.visited_cells

        for obj in env.objects:
            if obj.collected:
                continue
            if obj in self.discovered_objects:
                continue
            dx = abs(obj.x - rx)
            dy = abs(obj.y - ry)
            if dx + dy <= VISION_RANGE:
                # Objet repéré !
                self.discovered_objects.append(obj)
                print(f"   👀 Agent : {obj.name} repéré à ({obj.x},{obj.y}) !")

    def _is_target(self, obj) -> bool:
        """Vérifie si un objet correspond au type recherché."""
        if self.target_type == "all":
            return True
        return self.target_type in obj.name.lower()

    def start_mission(self, env, target_type: str, max_collect: int = 0):
        """Lance une mission d'exploration et collecte.
        max_collect=0 signifie 'toutes', sinon s'arrête après max_collect."""
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
        print(f"   🤖 Agent IA activé — objectif : {label}")
        print(f"   👁️  Champ de vision : {VISION_RANGE} cases")

        # Scan initial
        self._scan_surroundings(env)
        self._decide_next(env)

    def _decide_next(self, env):
        """Décide de la prochaine action : aller collecter un objet repéré ou explorer."""
        # Nettoyer les objets déjà collectés
        self.discovered_objects = [o for o in self.discovered_objects if not o.collected]

        # Y a-t-il un objet cible repéré ?
        targets_visible = [o for o in self.discovered_objects if self._is_target(o)]

        if targets_visible:
            # Aller vers le plus proche
            self.mode = "collecting"
            robot_pos = (int(env.position[0]), int(env.position[1]))
            best_obj = None
            best_path = None
            best_len = float("inf")

            for obj in targets_visible:
                path = bfs_path(env._map, robot_pos, obj.pos, env.grid_size)
                if path and len(path) < best_len:
                    best_len = len(path)
                    best_path = path
                    best_obj = obj

            if best_obj and best_path:
                self.current_target = best_obj
                actions = path_to_actions(best_path, env.orientation, grab_at_end=True)
                self.action_queue = deque(actions)
                self.status_message = f"→ {best_obj.name} repéré ! [{best_len - 1} pas]"
                print(f"   🎯 Agent : fonce vers {best_obj.name} à ({best_obj.x},{best_obj.y})")
                return

        # Sinon, explorer : aller vers la case walkable non visitée la plus proche
        self.mode = "exploring"
        self.current_target = None
        self._plan_exploration(env)

    def give_hint(self, env, landmark_name: str):
        """Reçoit un indice : l'objet cherché est près d'un repère."""
        for lm in env.landmarks:
            if lm.name == landmark_name:
                self.hint_position = lm.pos
                # Interrompre l'exploration en cours pour se diriger vers l'indice
                self.action_queue.clear()
                self._plan_exploration(env)
                self.status_message = f"Indice : près de {landmark_name} !"
                print(f"   💡 Agent : indice reçu — chercher près de {landmark_name} à ({lm.x},{lm.y})")
                return
        print(f"   ⚠️ Agent : repère '{landmark_name}' inconnu")

    def _plan_exploration(self, env):
        """Planifie un déplacement vers une zone non explorée.
        Si un indice est actif, priorise les cases proches du repère."""
        robot_pos = (int(env.position[0]), int(env.position[1]))
        grid_size = env.grid_size
        walkable = {1, 2}

        # Si on a un indice, aller vers les cases non visitées proches du repère
        if self.hint_position is not None:
            hx, hy = self.hint_position
            # Collecter toutes les cases marchables non visitées
            candidates = []
            for x in range(grid_size):
                for y in range(grid_size):
                    if (x, y) not in self.visited_cells and env._map[x, y] in walkable:
                        dist = abs(x - hx) + abs(y - hy)
                        candidates.append(((x, y), dist))
            # Trier par distance au repère
            candidates.sort(key=lambda c: c[1])
            # Si toutes les cases proches sont visitées, épuiser l'indice
            if not candidates:
                self.hint_position = None
            else:
                # Essayer les candidates dans l'ordre de proximité au repère
                for (tx, ty), _ in candidates:
                    path = bfs_path(env._map, robot_pos, (tx, ty), grid_size)
                    if path:
                        actions = path_to_actions(path, env.orientation, grab_at_end=False)
                        self.action_queue = deque(actions)
                        self.status_message = f"Indice : vers {self.hint_position}... ({len(self.visited_cells)} cases vues)"
                        return
                # Pas de chemin trouvé, abandonner l'indice
                self.hint_position = None

        # Exploration classique : BFS vers la case non visitée la plus proche
        visited_bfs = {robot_pos}
        parent = {}
        queue = deque([robot_pos])
        target = None

        while queue:
            cx, cy = queue.popleft()
            # Cette case est non visitée ?
            if (cx, cy) not in self.visited_cells and (cx, cy) != robot_pos:
                target = (cx, cy)
                break
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < grid_size and 0 <= ny < grid_size:
                    if (nx, ny) not in visited_bfs and env._map[nx, ny] in walkable:
                        visited_bfs.add((nx, ny))
                        parent[(nx, ny)] = (cx, cy)
                        queue.append((nx, ny))

        if target is None:
            # Toute la carte est explorée
            self.status_message = f"Carte explorée — {self.collected_count} collecté(s)"
            self.active = False
            env.fog_visited = None
            print(f"   🗺️  Agent : carte entièrement explorée. {self.collected_count} objet(s) collecté(s).")
            return

        # Reconstruire le chemin
        path = [target]
        while path[-1] != robot_pos:
            path.append(parent[path[-1]])
        path.reverse()

        actions = path_to_actions(path, env.orientation, grab_at_end=False)
        self.action_queue = deque(actions)
        self.status_message = f"Exploration... ({len(self.visited_cells)} cases vues)"

    def tick(self, env) -> int | None:
        """Appelé à chaque frame. Retourne la prochaine action ou None."""
        if not self.active:
            return None

        # Scanner à chaque pas
        self._scan_surroundings(env)

        # Vérifier si un objet cible vient d'être repéré pendant l'exploration
        if self.mode == "exploring":
            targets_visible = [o for o in self.discovered_objects
                               if self._is_target(o) and not o.collected]
            if targets_visible:
                # Interrompre l'exploration pour aller chercher l'objet
                self.action_queue.clear()
                self._decide_next(env)

        # Si on vient de finir de collecter, décider la suite
        if not self.action_queue:
            # Vérifier si on a ramassé l'objet courant
            if self.current_target and self.current_target.collected:
                self.collected_count += 1
                print(f"   ✨ Agent : {self.current_target.name} collecté ! ({self.collected_count} total)")
                self.current_target = None
                # Vérifier si l'objectif est atteint
                if self.max_collect > 0 and self.collected_count >= self.max_collect:
                    self.status_message = f"Mission accomplie ! ({self.collected_count} collectés)"
                    self.active = False
                    env.fog_visited = None
                    print(f"   🎉 Agent : objectif atteint — {self.collected_count}/{self.max_collect} collecté(s) !")
                    return None
            self._decide_next(env)
            if not self.action_queue:
                return None

        return self.action_queue.popleft()

    def cancel(self):
        """Annule la mission en cours."""
        self.active = False
        self.action_queue.clear()
        self.discovered_objects = []
        self.current_target = None
        self.status_message = "Mission annulée"
        print("   🛑 Agent IA : mission annulée")

    def cancel_with_env(self, env):
        """Annule la mission et nettoie le fog."""
        self.cancel()
        env.fog_visited = None
