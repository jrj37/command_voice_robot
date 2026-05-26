"""
Environnement Gymnasium personnalisé : un robot sur une carte de ville
avec routes, herbe, bâtiments et arbres — contrôlable vocalement.
"""

import gymnasium as gym
import numpy as np
from gymnasium import spaces
import pygame
import math
import time

from objects import CollectibleObject, spawn_objects, Landmark, spawn_landmarks


# ─── Couleurs ───────────────────────────────────────────────
C_GRASS       = (76, 153, 76)
C_GRASS_DARK  = (60, 130, 60)
C_ROAD        = (64, 64, 64)
C_ROAD_LINE   = (200, 200, 80)
C_SIDEWALK    = (160, 160, 150)
C_BUILDING_1  = (120, 90, 80)
C_BUILDING_2  = (100, 110, 140)
C_BUILDING_3  = (140, 120, 100)
C_WINDOW      = (220, 220, 160)
C_TREE_TRUNK  = (100, 70, 40)
C_TREE_TOP    = (30, 140, 50)
C_TREE_TOP2   = (50, 170, 60)
C_ROBOT_BODY  = (40, 180, 220)
C_ROBOT_HEAD  = (255, 100, 80)
C_ROBOT_EYE   = (255, 255, 255)
C_HUD_BG      = (20, 20, 30, 220)
C_HUD_TEXT    = (220, 220, 220)
C_HUD_ACCENT  = (80, 200, 255)
C_MIC_ON      = (80, 220, 120)
C_MIC_OFF     = (220, 60, 60)
C_GRAB_CLAW   = (180, 180, 190)
C_GRAB_GLOW   = (255, 255, 100)
C_INVENTORY   = (255, 200, 60)


class RobotEnv(gym.Env):
    """Robot sur une carte de ville stylisée."""

    metadata = {"render_modes": ["human"], "render_fps": 10}

    DIRECTION_NAMES = {0: "Nord ↑", 1: "Est →", 2: "Sud ↓", 3: "Ouest ←"}
    DIRECTION_DELTAS = {
        0: np.array([0, -1]),
        1: np.array([1, 0]),
        2: np.array([0, 1]),
        3: np.array([-1, 0]),
    }

    # Routes : colonnes et rangées qui forment les rues
    ROAD_COLS = {2, 5, 8}
    ROAD_ROWS = {2, 5, 8}

    def __init__(self, render_mode="human", grid_size=11):
        super().__init__()
        self.grid_size = grid_size
        self.render_mode = render_mode
        self.cell_size = 64

        # 0=avancer, 1=gauche, 2=droite, 3=ramasser
        self.action_space = spaces.Discrete(4)
        self.observation_space = spaces.Box(
            low=np.array([0, 0, 0]),
            high=np.array([grid_size - 1, grid_size - 1, 3]),
            dtype=np.int32,
        )

        self.position = np.array([5, 5], dtype=np.int32)
        self.orientation = 0
        self.trail = []  # trace du chemin parcouru
        self.mic_active = False
        self.last_command = ""

        # Objets & inventaire
        self.objects: list[CollectibleObject] = []
        self.inventory: list[CollectibleObject] = []
        self.grab_anim_frame = 0      # 0 = pas d'animation
        self.grab_anim_max = 12       # durée animation en frames
        self.grab_target = None       # objet en cours de ramassage
        self.grab_message = ""        # message affiché après ramassage
        self.grab_message_timer = 0
        self.fog_visited: set[tuple[int, int]] | None = None  # None = pas de fog

        self.window = None
        self.clock = None
        self._map = self._generate_map()
        # Seed-based random decorations
        self._rng = np.random.RandomState(42)
        self._decorations = self._generate_decorations()
        # Spawn objects on valid tiles
        self.objects = spawn_objects(self._map, self.grid_size)
        # Spawn landmarks on sidewalks
        used = {o.pos for o in self.objects}
        self.landmarks: list[Landmark] = spawn_landmarks(self._map, self.grid_size, used)

    def _generate_map(self):
        """0=herbe, 1=route, 2=trottoir, 3=bâtiment"""
        grid = np.zeros((self.grid_size, self.grid_size), dtype=np.int8)
        for x in range(self.grid_size):
            for y in range(self.grid_size):
                if x in self.ROAD_COLS or y in self.ROAD_ROWS:
                    grid[x, y] = 1  # route
                    # Trottoirs adjacents
                    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < self.grid_size and 0 <= ny < self.grid_size:
                            if grid[nx, ny] == 0:
                                grid[nx, ny] = 2  # trottoir
        # Bâtiments sur certaines cases herbe restantes
        for x in range(self.grid_size):
            for y in range(self.grid_size):
                if grid[x, y] == 0:
                    grid[x, y] = 3  # bâtiment / parc
        return grid

    def _generate_decorations(self):
        """Génère des décorations aléatoires pour les bâtiments et arbres."""
        decos = {}
        for x in range(self.grid_size):
            for y in range(self.grid_size):
                if self._map[x, y] == 3:
                    decos[(x, y)] = {
                        "type": self._rng.choice(["building", "tree", "tree"]),
                        "color_idx": self._rng.randint(0, 3),
                        "height": self._rng.uniform(0.5, 0.9),
                        "windows": self._rng.randint(1, 5),
                    }
                elif self._map[x, y] == 2:
                    if self._rng.random() < 0.2:
                        decos[(x, y)] = {"type": "small_tree"}
        return decos

    def set_mic_active(self, active):
        self.mic_active = active

    def set_last_command(self, cmd):
        self.last_command = cmd

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        self.position = np.array([5, 5], dtype=np.int32)
        self.orientation = 0
        self.trail = []
        self.last_command = ""
        self.inventory = []
        self.grab_anim_frame = 0
        self.grab_target = None
        self.grab_message = ""
        self.grab_message_timer = 0
        self.fog_visited = None
        # Re-spawn objects & landmarks
        self.objects = spawn_objects(self._map, self.grid_size)
        used = {o.pos for o in self.objects}
        self.landmarks = spawn_landmarks(self._map, self.grid_size, used)
        obs = self._get_obs()
        if self.render_mode == "human":
            self.render()
        return obs, {}

    def step(self, action):
        old_pos = self.position.copy()

        if action == 0:
            delta = self.DIRECTION_DELTAS[self.orientation]
            new_pos = self.position + delta
            new_pos = np.clip(new_pos, 0, self.grid_size - 1)
            self.position = new_pos
        elif action == 1:
            self.orientation = (self.orientation - 1) % 4
        elif action == 2:
            self.orientation = (self.orientation + 1) % 4
        elif action == 3:
            self._try_grab()

        if not np.array_equal(old_pos, self.position):
            self.trail.append(tuple(old_pos))
            if len(self.trail) > 50:
                self.trail.pop(0)

        obs = self._get_obs()
        if self.render_mode == "human":
            self.render()
        return obs, 0.0, False, False, {}

    def _try_grab(self):
        """Tente de ramasser un objet devant ou sous le robot."""
        # Cases à vérifier : sous le robot + case devant
        front = self.position + self.DIRECTION_DELTAS[self.orientation]
        front = np.clip(front, 0, self.grid_size - 1)
        check_positions = [
            (self.position[0], self.position[1]),  # sous le robot
            (int(front[0]), int(front[1])),         # devant
        ]

        for obj in self.objects:
            if obj.collected:
                continue
            if obj.pos in check_positions:
                # Lancer l'animation
                obj.collected = True
                self.inventory.append(obj)
                self.grab_anim_frame = self.grab_anim_max
                self.grab_target = obj
                self.grab_message = f"Ramassé : {obj.name} !"
                self.grab_message_timer = 60  # ~2 secondes à 30fps
                return

        # Rien à ramasser
        self.grab_message = "Rien à ramasser ici"
        self.grab_message_timer = 40

    def get_nearby_objects(self) -> list[CollectibleObject]:
        """Retourne les objets proches du robot (distance ≤ 1)."""
        nearby = []
        for obj in self.objects:
            if obj.collected:
                continue
            dx = abs(obj.x - self.position[0])
            dy = abs(obj.y - self.position[1])
            if dx + dy <= 1:
                nearby.append(obj)
        return nearby

    def _get_obs(self):
        return np.array([self.position[0], self.position[1], self.orientation], dtype=np.int32)

    # ─── Rendu ──────────────────────────────────────────────────
    def render(self):
        if self.render_mode != "human":
            return

        cs = self.cell_size
        ws = self.grid_size * cs
        hud_h = 64

        if self.window is None:
            pygame.init()
            self.window = pygame.display.set_mode((ws, ws + hud_h))
            pygame.display.set_caption("Robot Voice Control")
            self.clock = pygame.time.Clock()
            self.font_sm = pygame.font.SysFont("Menlo", 13)
            self.font_md = pygame.font.SysFont("Menlo", 15, bold=True)
            self.font_lg = pygame.font.SysFont("Menlo", 20, bold=True)

        surface = self.window

        # ── Fond carte ──
        for x in range(self.grid_size):
            for y in range(self.grid_size):
                rect = pygame.Rect(x * cs, y * cs, cs, cs)
                cell = self._map[x, y]
                if cell == 1:
                    pygame.draw.rect(surface, C_ROAD, rect)
                    self._draw_road_markings(surface, x, y, cs)
                elif cell == 2:
                    pygame.draw.rect(surface, C_SIDEWALK, rect)
                    # Petits pavés
                    for i in range(0, cs, 8):
                        pygame.draw.line(surface, (145, 145, 135),
                                         (x * cs + i, y * cs), (x * cs + i, y * cs + cs - 1), 1)
                elif cell == 3:
                    pygame.draw.rect(surface, C_GRASS, rect)
                    # Texture herbe
                    if (x + y) % 2 == 0:
                        pygame.draw.rect(surface, C_GRASS_DARK, rect.inflate(-8, -8))
                else:
                    pygame.draw.rect(surface, C_GRASS, rect)

        # ── Décorations (bâtiments & arbres) ──
        for (x, y), deco in self._decorations.items():
            cx_d = x * cs + cs // 2
            cy_d = y * cs + cs // 2
            if deco["type"] == "building":
                colors = [C_BUILDING_1, C_BUILDING_2, C_BUILDING_3]
                col = colors[deco["color_idx"]]
                h = int(cs * deco["height"])
                w = int(cs * 0.7)
                br = pygame.Rect(cx_d - w // 2, cy_d - h // 2, w, h)
                pygame.draw.rect(surface, col, br)
                pygame.draw.rect(surface, (50, 50, 50), br, 2)
                # Fenêtres
                for wi in range(deco["windows"]):
                    wy = br.top + 6 + wi * 10
                    if wy + 6 > br.bottom:
                        break
                    pygame.draw.rect(surface, C_WINDOW,
                                     (br.left + 5, wy, 6, 6))
                    pygame.draw.rect(surface, C_WINDOW,
                                     (br.right - 11, wy, 6, 6))
            elif deco["type"] == "tree":
                self._draw_tree(surface, cx_d, cy_d, cs)
            elif deco["type"] == "small_tree":
                self._draw_small_tree(surface, cx_d, cy_d, cs)

        # ── Trail (trace du robot) ──
        for i, (tx, ty) in enumerate(self.trail):
            alpha = 80 + int(120 * i / max(len(self.trail), 1))
            tcx = tx * cs + cs // 2
            tcy = ty * cs + cs // 2
            trail_surf = pygame.Surface((10, 10), pygame.SRCALPHA)
            pygame.draw.circle(trail_surf, (80, 200, 255, alpha), (5, 5), 4)
            surface.blit(trail_surf, (tcx - 5, tcy - 5))

        # ── Repères (landmarks) ──
        self._draw_landmarks(surface, cs)

        # ── Objets collectibles ──
        self._draw_objects(surface, cs)

        # ── Robot ──
        self._draw_robot(surface, cs)

        # ── Brouillard de guerre (fog of war) ──
        if self.fog_visited is not None:
            self._draw_fog_of_war(surface, cs)

        # ── Animation pince ──
        if self.grab_anim_frame > 0:
            self._draw_grab_animation(surface, cs)
            self.grab_anim_frame -= 1

        # ── Message de ramassage ──
        if self.grab_message_timer > 0:
            self._draw_grab_message(surface, ws)
            self.grab_message_timer -= 1

        # ── HUD en bas ──
        self._draw_hud(surface, ws, hud_h)

        pygame.display.flip()
        self.clock.tick(self.metadata["render_fps"])

    def _draw_road_markings(self, surface, x, y, cs):
        """Lignes pointillées au centre des routes."""
        px, py = x * cs, y * cs
        # Ligne horizontale
        if y in self.ROAD_ROWS:
            for i in range(0, cs, 12):
                pygame.draw.line(surface, C_ROAD_LINE,
                                 (px + i, py + cs // 2), (px + i + 6, py + cs // 2), 1)
        # Ligne verticale
        if x in self.ROAD_COLS:
            for i in range(0, cs, 12):
                pygame.draw.line(surface, C_ROAD_LINE,
                                 (px + cs // 2, py + i), (px + cs // 2, py + i + 6), 1)

    def _draw_tree(self, surface, cx, cy, cs):
        r = cs // 4
        pygame.draw.rect(surface, C_TREE_TRUNK, (cx - 3, cy, 6, r))
        pygame.draw.circle(surface, C_TREE_TOP, (cx, cy - 2), r)
        pygame.draw.circle(surface, C_TREE_TOP2, (cx - 4, cy - 6), r - 3)

    def _draw_small_tree(self, surface, cx, cy, cs):
        r = cs // 7
        pygame.draw.rect(surface, C_TREE_TRUNK, (cx - 2, cy + 2, 4, r))
        pygame.draw.circle(surface, C_TREE_TOP2, (cx, cy), r)

    def _draw_robot(self, surface, cs):
        """Dessine un robot mignon avec un corps, une tête et des yeux."""
        cx = self.position[0] * cs + cs // 2
        cy = self.position[1] * cs + cs // 2
        angle_map = {0: -90, 1: 0, 2: 90, 3: 180}
        angle = angle_map[self.orientation]
        angle_rad = math.radians(angle)

        # Ombre
        shadow = pygame.Surface((cs, cs), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 60), (8, 12, cs - 16, cs - 20))
        surface.blit(shadow, (cx - cs // 2, cy - cs // 2 + 4))

        # Corps (cercle principal)
        body_r = cs // 3
        pygame.draw.circle(surface, C_ROBOT_BODY, (cx, cy), body_r)
        pygame.draw.circle(surface, (30, 160, 200), (cx, cy), body_r, 2)

        # Indicateur de direction (flèche)
        arrow_len = body_r + 8
        tip_x = cx + int(arrow_len * math.cos(angle_rad))
        tip_y = cy + int(arrow_len * math.sin(angle_rad))

        # Pointe
        left_a = angle_rad + 2.6
        right_a = angle_rad - 2.6
        l_x = cx + int((body_r + 2) * math.cos(left_a))
        l_y = cy + int((body_r + 2) * math.sin(left_a))
        r_x = cx + int((body_r + 2) * math.cos(right_a))
        r_y = cy + int((body_r + 2) * math.sin(right_a))
        pygame.draw.polygon(surface, C_ROBOT_HEAD, [(tip_x, tip_y), (l_x, l_y), (r_x, r_y)])

        # Yeux (positionnés selon l'orientation)
        eye_dist = body_r // 3
        eye_r = 4
        perp_rad = angle_rad + math.pi / 2
        for side in (-1, 1):
            ex = cx + int((body_r * 0.3) * math.cos(angle_rad)) + int(eye_dist * side * math.cos(perp_rad))
            ey = cy + int((body_r * 0.3) * math.sin(angle_rad)) + int(eye_dist * side * math.sin(perp_rad))
            pygame.draw.circle(surface, C_ROBOT_EYE, (ex, ey), eye_r)
            # Pupille
            px = ex + int(2 * math.cos(angle_rad))
            py = ey + int(2 * math.sin(angle_rad))
            pygame.draw.circle(surface, (30, 30, 30), (px, py), 2)

        # Antenne
        ant_x = cx - int((body_r * 0.5) * math.cos(angle_rad))
        ant_y = cy - int((body_r * 0.5) * math.sin(angle_rad))
        ant_tip_x = ant_x - int(12 * math.cos(angle_rad))
        ant_tip_y = ant_y - int(12 * math.sin(angle_rad))
        pygame.draw.line(surface, (200, 200, 200), (ant_x, ant_y), (ant_tip_x, ant_tip_y), 2)
        pygame.draw.circle(surface, C_ROBOT_HEAD, (ant_tip_x, ant_tip_y), 3)

    def _draw_landmarks(self, surface, cs):
        """Dessine les repères identifiables sur la carte."""
        for lm in self.landmarks:
            cx = lm.x * cs + cs // 2
            cy = lm.y * cs + cs // 2
            col = lm.color

            if lm.shape == "fountain":
                # Bassin circulaire + jet d'eau
                pygame.draw.circle(surface, (80, 130, 200), (cx, cy), cs // 3, 3)
                pygame.draw.circle(surface, col, (cx, cy), cs // 5)
                # Jet
                tick = pygame.time.get_ticks() / 400.0
                jh = int(6 + 3 * math.sin(tick))
                pygame.draw.line(surface, (180, 220, 255), (cx, cy), (cx, cy - jh), 2)
                pygame.draw.circle(surface, (180, 220, 255), (cx, cy - jh), 3)

            elif lm.shape == "statue":
                # Piédestal + buste
                pw, ph = cs // 3, cs // 6
                pygame.draw.rect(surface, (140, 130, 120),
                                 (cx - pw // 2, cy + 4, pw, ph))
                # Buste (tête + épaules)
                pygame.draw.circle(surface, col, (cx, cy - 4), cs // 6)
                pygame.draw.rect(surface, col,
                                 (cx - cs // 5, cy + 1, cs * 2 // 5, 4))

            elif lm.shape == "bench":
                # Banc vu du dessus
                bw, bh = cs // 2, cs // 5
                pygame.draw.rect(surface, col,
                                 (cx - bw // 2, cy - bh // 2, bw, bh),
                                 border_radius=3)
                # Pieds
                pygame.draw.rect(surface, (100, 80, 50),
                                 (cx - bw // 2 + 2, cy + bh // 2, 4, 4))
                pygame.draw.rect(surface, (100, 80, 50),
                                 (cx + bw // 2 - 6, cy + bh // 2, 4, 4))

            elif lm.shape == "lamp":
                # Poteau + halo
                pygame.draw.rect(surface, (100, 100, 110),
                                 (cx - 2, cy - cs // 4, 4, cs // 2))
                # Ampoule avec halo
                glow = pygame.Surface((24, 24), pygame.SRCALPHA)
                tick = pygame.time.get_ticks() / 500.0
                alpha = int(80 + 30 * math.sin(tick))
                pygame.draw.circle(glow, (*col, alpha), (12, 12), 12)
                surface.blit(glow, (cx - 12, cy - cs // 4 - 16))
                pygame.draw.circle(surface, col, (cx, cy - cs // 4 - 4), 5)

            elif lm.shape == "sign":
                # Poteau + panneau
                pygame.draw.rect(surface, (100, 100, 110),
                                 (cx - 1, cy - 2, 3, cs // 3))
                pw, ph = cs // 3, cs // 4
                pygame.draw.rect(surface, col,
                                 (cx - pw // 2, cy - cs // 4 - 2, pw, ph),
                                 border_radius=2)
                pygame.draw.rect(surface, (255, 255, 255),
                                 (cx - pw // 2, cy - cs // 4 - 2, pw, ph),
                                 1, border_radius=2)

            # Label texte sous le repère
            label = self.font_sm.render(lm.name, True, (255, 255, 255))
            lbl_bg = pygame.Surface((label.get_width() + 4, label.get_height() + 2), pygame.SRCALPHA)
            lbl_bg.fill((0, 0, 0, 120))
            surface.blit(lbl_bg, (cx - label.get_width() // 2 - 2, cy + cs // 3))
            surface.blit(label, (cx - label.get_width() // 2, cy + cs // 3 + 1))

    def _draw_fog_of_war(self, surface, cs):
        """Assombrit les cases non encore visitées par l'agent."""
        fog_surf = pygame.Surface((cs, cs), pygame.SRCALPHA)
        fog_surf.fill((0, 0, 0, 140))
        for x in range(self.grid_size):
            for y in range(self.grid_size):
                if (x, y) not in self.fog_visited:
                    surface.blit(fog_surf, (x * cs, y * cs))

    def _draw_objects(self, surface, cs):
        """Dessine les objets collectibles sur la carte."""
        tick = pygame.time.get_ticks() / 1000.0
        for obj in self.objects:
            if obj.collected:
                continue
            cx = obj.x * cs + cs // 2
            cy = obj.y * cs + cs // 2
            # Flottement vertical
            bob = int(3 * math.sin(tick * 2.5 + obj.anim_offset))
            cy += bob

            # Halo lumineux
            glow_r = cs // 3
            glow_surf = pygame.Surface((glow_r * 2, glow_r * 2), pygame.SRCALPHA)
            alpha = int(60 + 30 * math.sin(tick * 3 + obj.anim_offset))
            pygame.draw.circle(glow_surf, (*obj.color, alpha), (glow_r, glow_r), glow_r)
            surface.blit(glow_surf, (cx - glow_r, cy - glow_r))

            # Forme selon le type
            self._draw_object_shape(surface, obj, cx, cy, cs)

    def _draw_object_shape(self, surface, obj, cx, cy, cs):
        """Dessine la forme de l'objet."""
        r = cs // 5
        col = obj.color

        if obj.shape == "key":
            # Cercle + tige
            pygame.draw.circle(surface, col, (cx - 4, cy - 2), r - 2, 3)
            pygame.draw.rect(surface, col, (cx, cy - 2, r + 4, 4))
            pygame.draw.rect(surface, col, (cx + r, cy - 5, 3, 7))
            pygame.draw.rect(surface, col, (cx + r - 5, cy - 5, 3, 7))
        elif obj.shape == "diamond":
            pts = [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)]
            pygame.draw.polygon(surface, col, pts)
            pygame.draw.polygon(surface, (255, 255, 255), pts, 2)
        elif obj.shape == "star":
            self._draw_star(surface, cx, cy, r, 5, col)
        elif obj.shape == "coin":
            pygame.draw.circle(surface, col, (cx, cy), r)
            pygame.draw.circle(surface, (255, 230, 100), (cx, cy), r - 3)
            pygame.draw.circle(surface, col, (cx, cy), r, 2)
        elif obj.shape == "battery":
            bw, bh = r + 4, r * 2
            br = pygame.Rect(cx - bw // 2, cy - bh // 2, bw, bh)
            pygame.draw.rect(surface, col, br, border_radius=3)
            pygame.draw.rect(surface, (40, 40, 40), br, 2, border_radius=3)
            # Borne
            pygame.draw.rect(surface, col, (cx - 3, cy - bh // 2 - 4, 6, 5))

    def _draw_star(self, surface, cx, cy, r, points, color):
        """Dessine une étoile."""
        pts = []
        for i in range(points * 2):
            angle = math.radians(-90) + i * math.pi / points
            rad = r if i % 2 == 0 else r * 0.45
            pts.append((cx + int(rad * math.cos(angle)),
                        cy + int(rad * math.sin(angle))))
        pygame.draw.polygon(surface, color, pts)
        pygame.draw.polygon(surface, (255, 255, 255), pts, 1)

    def _draw_grab_animation(self, surface, cs):
        """Dessine l'animation de la pince qui attrape."""
        cx = self.position[0] * cs + cs // 2
        cy = self.position[1] * cs + cs // 2
        angle_map = {0: -90, 1: 0, 2: 90, 3: 180}
        angle_rad = math.radians(angle_map[self.orientation])

        progress = 1.0 - (self.grab_anim_frame / self.grab_anim_max)
        # Phase 1 : pince s'ouvre et avance, Phase 2 : pince se ferme et recule
        if progress < 0.5:
            t = progress * 2  # 0→1 pendant phase 1
            extend = t
            claw_open = 0.3 + t * 0.4  # s'ouvre
        else:
            t = (progress - 0.5) * 2  # 0→1 pendant phase 2
            extend = 1.0 - t
            claw_open = 0.7 - t * 0.6  # se ferme

        # Distance d'extension de la pince
        arm_len = int(cs * 0.3 + cs * 0.5 * extend)

        # Point d'attache sur le robot
        arm_x = cx + int(arm_len * math.cos(angle_rad))
        arm_y = cy + int(arm_len * math.sin(angle_rad))

        # Bras
        pygame.draw.line(surface, C_GRAB_CLAW, (cx, cy), (arm_x, arm_y), 4)

        # Deux griffes
        claw_len = int(cs * 0.25)
        perp_rad = angle_rad + math.pi / 2
        spread = claw_open * 0.6

        for side in (-1, 1):
            claw_angle = angle_rad + side * spread
            c_x = arm_x + int(claw_len * math.cos(claw_angle))
            c_y = arm_y + int(claw_len * math.sin(claw_angle))
            pygame.draw.line(surface, C_GRAB_CLAW, (arm_x, arm_y), (c_x, c_y), 3)
            # Bout de griffe
            tip_angle = claw_angle + side * 0.8
            t_x = c_x + int(6 * math.cos(tip_angle))
            t_y = c_y + int(6 * math.sin(tip_angle))
            pygame.draw.line(surface, C_GRAB_CLAW, (c_x, c_y), (t_x, t_y), 3)

        # Particules si on attrape quelque chose
        if self.grab_target and progress > 0.4:
            for i in range(4):
                pa = angle_rad + i * math.pi / 2
                sparkle_r = int(8 * (1.0 - progress))
                px = arm_x + int(sparkle_r * 2 * math.cos(pa + progress * 5))
                py = arm_y + int(sparkle_r * 2 * math.sin(pa + progress * 5))
                spark_surf = pygame.Surface((sparkle_r * 2, sparkle_r * 2), pygame.SRCALPHA)
                alpha = int(200 * (1.0 - progress))
                pygame.draw.circle(spark_surf, (*C_GRAB_GLOW, alpha),
                                   (sparkle_r, sparkle_r), max(sparkle_r, 1))
                surface.blit(spark_surf, (px - sparkle_r, py - sparkle_r))

    def _draw_grab_message(self, surface, ws):
        """Affiche un message flottant au centre de l'écran."""
        alpha = min(255, self.grab_message_timer * 8)
        msg_surf = pygame.Surface((ws, 40), pygame.SRCALPHA)
        pygame.draw.rect(msg_surf, (20, 20, 30, min(200, alpha)),
                         (0, 0, ws, 40), border_radius=8)
        txt = self.font_lg.render(self.grab_message, True, C_INVENTORY)
        msg_surf.blit(txt, (ws // 2 - txt.get_width() // 2, 8))
        # Positionner en haut de l'écran
        bob = int(3 * math.sin(pygame.time.get_ticks() / 200.0))
        surface.blit(msg_surf, (0, 20 + bob))

    def _draw_hud(self, surface, ws, hud_h):
        """Barre d'info en bas."""
        hud_rect = pygame.Rect(0, ws, ws, hud_h)
        pygame.draw.rect(surface, (18, 18, 28), hud_rect)
        pygame.draw.line(surface, C_HUD_ACCENT, (0, ws), (ws, ws), 2)

        direction = self.DIRECTION_NAMES[self.orientation]
        pos_text = f"({self.position[0]}, {self.position[1]})"

        # Position
        lbl = self.font_sm.render("POS", True, (120, 120, 140))
        surface.blit(lbl, (12, ws + 8))
        val = self.font_md.render(pos_text, True, C_HUD_ACCENT)
        surface.blit(val, (12, ws + 26))

        # Direction
        lbl2 = self.font_sm.render("DIR", True, (120, 120, 140))
        surface.blit(lbl2, (110, ws + 8))
        val2 = self.font_md.render(direction, True, C_HUD_ACCENT)
        surface.blit(val2, (110, ws + 26))

        # Mic status
        mic_col = C_MIC_ON if self.mic_active else C_MIC_OFF
        mic_label = "MIC ON" if self.mic_active else "MIC OFF"
        pygame.draw.circle(surface, mic_col, (250, ws + 24), 6)
        mic_txt = self.font_sm.render(mic_label, True, mic_col)
        surface.blit(mic_txt, (262, ws + 17))

        # Inventaire
        inv_count = len(self.inventory)
        total = len(self.objects)
        inv_txt = self.font_md.render(f"INV: {inv_count}/{total}", True, C_INVENTORY)
        surface.blit(inv_txt, (340, ws + 8))

        # Objets proches
        nearby = self.get_nearby_objects()
        if nearby:
            near_txt = self.font_sm.render(
                f">> {nearby[0].name} à portée !", True, (255, 220, 80))
            surface.blit(near_txt, (340, ws + 30))
        else:
            near_txt = self.font_sm.render("Rien à portée", True, (80, 80, 100))
            surface.blit(near_txt, (340, ws + 30))

        # Dernière commande
        if self.last_command:
            cmd_txt = self.font_sm.render(f'"{self.last_command}"', True, (180, 180, 100))
            surface.blit(cmd_txt, (500, ws + 8))

        # Commandes aide
        help_txt = self.font_sm.render("avance | gauche | droite | ramasse | stop", True, (80, 80, 100))
        surface.blit(help_txt, (ws - 370, ws + 48))

    def close(self):
        if self.window is not None:
            pygame.quit()
            self.window = None
