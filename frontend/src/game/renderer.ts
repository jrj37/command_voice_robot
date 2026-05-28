import { Application, Container, Graphics, Ticker } from "pixi.js";
import { PALETTE } from "./colors";
import type { StaticPayload, StatePayload, ObjectData, GrabEvent } from "../net/types";

// Rendu moderne (non pixel-art) : antialiasing, formes lisses, dégradés simulés
// par superposition de cercles/rectangles. Le robot se déplace case par case
// (snap instantané), avec un petit "pop" de feedback à l'arrivée.
const CELL = 56;
const GRID = 11;

interface Particle {
  x: number; y: number; vx: number; vy: number;
  life: number; maxLife: number; color: number; size: number;
}

export class GameRenderer {
  app: Application;
  private bgLayer = new Container();
  private gridLayer = new Container();
  private decoLayer = new Container();
  private trailLayer = new Container();
  private landmarkLayer = new Container();
  private objectLayer = new Container();
  private robotLayer = new Container();
  private fxLayer = new Container();
  private fogLayer = new Container();

  private robotG = new Graphics();
  private robotShadow = new Graphics();

  private staticData: StaticPayload | null = null;
  private state: StatePayload | null = null;

  // Position robot — snap case par case
  private robotPos = { x: 5, y: 5, dir: 0 };
  private arrivePulse = 0; // 0→1 puis redescend, petit "pop" à l'arrivée
  private particles: Particle[] = [];
  private clock = 0;

  private knownObjects = new Map<number, ObjectData>();

  private initialized = false;
  private destroyed = false;
  private initPromise: Promise<void>;

  constructor(canvas: HTMLCanvasElement) {
    this.app = new Application();
    this.initPromise = this.init(canvas).catch((e) => {
      console.warn("GameRenderer init failed:", e);
    });
  }

  private async init(canvas: HTMLCanvasElement) {
    await this.app.init({
      canvas,
      width: GRID * CELL,
      height: GRID * CELL,
      backgroundAlpha: 0,
      antialias: true,
      resolution: window.devicePixelRatio || 1,
      autoDensity: true,
    });

    if (this.destroyed) {
      try { this.app.destroy(true, { children: true }); } catch { /* ignore */ }
      return;
    }

    const root = new Container();
    root.addChild(
      this.bgLayer,
      this.gridLayer,
      this.decoLayer,
      this.trailLayer,
      this.landmarkLayer,
      this.objectLayer,
      this.fogLayer,
      this.robotShadow,
      this.robotLayer,
      this.fxLayer,
    );
    this.app.stage.addChild(root);
    this.robotLayer.addChild(this.robotG);
    this.app.ticker.add((t) => this.tick(t));
    this.initialized = true;

    if (this.staticData) {
      this.drawBackground();
      this.drawGridOverlay();
      this.drawDecorations();
      this.drawLandmarks();
    }
    if (this.state) {
      this.drawTrail();
      this.drawObjects();
      this.drawFog();
    }
  }

  get gridPx() {
    return GRID * CELL;
  }

  setStatic(payload: StaticPayload) {
    this.staticData = payload;
    if (!this.initialized) return;
    this.drawBackground();
    this.drawGridOverlay();
    this.drawDecorations();
    this.drawLandmarks();
  }

  setState(state: StatePayload) {
    if (state.grab_event?.success && state.grab_event.x !== undefined && state.grab_event.y !== undefined) {
      this.spawnGrabBurst(state.grab_event);
    }
    for (const o of state.objects) {
      const prev = this.knownObjects.get(o.id);
      if (prev && !prev.collected && o.collected) this.spawnCollectBurst(o);
      this.knownObjects.set(o.id, o);
    }

    // ── Mouvement case par case : snap, pas d'interpolation. ──
    const moved =
      !this.state ||
      this.state.robot.x !== state.robot.x ||
      this.state.robot.y !== state.robot.y ||
      this.state.robot.dir !== state.robot.dir;
    if (moved) {
      this.robotPos = { x: state.robot.x, y: state.robot.y, dir: state.robot.dir };
      this.arrivePulse = 1;
    }

    this.state = state;
    if (!this.initialized) return;
    this.drawTrail();
    this.drawObjects();
    this.drawFog();
  }

  private tick(t: Ticker) {
    const dt = t.deltaMS / 1000;
    this.clock += dt;
    // Décroissance du pulse d'arrivée
    if (this.arrivePulse > 0) {
      this.arrivePulse = Math.max(0, this.arrivePulse - dt * 5);
    }
    this.drawRobot();
    this.drawParticles(dt);
    this.pulseObjects();
  }

  // ── Background : tuiles douces avec variations subtiles ─────────────
  private drawBackground() {
    if (!this.staticData) return;
    this.bgLayer.removeChildren();
    const g = new Graphics();
    const { grid_size, map } = this.staticData;

    // Fond global (très légère teinte slate)
    g.rect(0, 0, grid_size * CELL, grid_size * CELL).fill(0x0e1120);

    for (let x = 0; x < grid_size; x++) {
      for (let y = 0; y < grid_size; y++) {
        const cell = map[x][y];
        const px = x * CELL, py = y * CELL;

        if (cell === 1) {
          // Route — fond sombre + chaussée centrale
          g.roundRect(px + 1, py + 1, CELL - 2, CELL - 2, 6).fill(PALETTE.road);
          this.drawRoadMarkings(g, x, y, px, py);
        } else if (cell === 2) {
          // Trottoir
          g.roundRect(px + 1, py + 1, CELL - 2, CELL - 2, 6).fill(PALETTE.sidewalk);
          // léger highlight haut/gauche pour la profondeur
          g.roundRect(px + 2, py + 2, CELL - 4, 2, 2).fill({ color: PALETTE.sidewalkLight, alpha: 0.6 });
        } else if (cell === 3) {
          // Herbe
          g.roundRect(px + 1, py + 1, CELL - 2, CELL - 2, 6).fill(PALETTE.grass);
          // Petite tache plus claire pour texture
          if ((x + y) % 2 === 0) {
            g.roundRect(px + 8, py + 8, CELL - 16, CELL - 16, 4)
              .fill({ color: PALETTE.grassLight, alpha: 0.4 });
          }
        } else {
          // Autres
          g.roundRect(px + 1, py + 1, CELL - 2, CELL - 2, 6).fill(0x141728);
        }
      }
    }
    this.bgLayer.addChild(g);
  }

  private drawRoadMarkings(g: Graphics, gx: number, gy: number, px: number, py: number) {
    const ROAD_COLS = new Set([2, 5, 8]);
    const ROAD_ROWS = new Set([2, 5, 8]);
    // Pointillés horizontaux
    if (ROAD_ROWS.has(gy)) {
      for (let i = 6; i < CELL - 6; i += 10) {
        g.roundRect(px + i, py + CELL / 2 - 1.5, 6, 3, 1.5)
          .fill({ color: PALETTE.roadLine, alpha: 0.85 });
      }
    }
    // Pointillés verticaux
    if (ROAD_COLS.has(gx)) {
      for (let i = 6; i < CELL - 6; i += 10) {
        g.roundRect(px + CELL / 2 - 1.5, py + i, 3, 6, 1.5)
          .fill({ color: PALETTE.roadLine, alpha: 0.85 });
      }
    }
  }

  private drawGridOverlay() {
    if (!this.staticData) return;
    this.gridLayer.removeChildren();
    const g = new Graphics();
    const size = this.staticData.grid_size;
    // Lignes très discrètes (1px, faible alpha)
    for (let i = 0; i <= size; i++) {
      g.moveTo(0, i * CELL).lineTo(size * CELL, i * CELL)
        .stroke({ width: 1, color: 0xffffff, alpha: 0.025 });
      g.moveTo(i * CELL, 0).lineTo(i * CELL, size * CELL)
        .stroke({ width: 1, color: 0xffffff, alpha: 0.025 });
    }
    this.gridLayer.addChild(g);
  }

  // ── Décorations : buildings arrondis, arbres lisses ─────────────────
  private drawDecorations() {
    if (!this.staticData) return;
    this.decoLayer.removeChildren();
    const g = new Graphics();
    const buildingColors = [PALETTE.building1, PALETTE.building2, PALETTE.building3];

    for (const d of this.staticData.decorations) {
      const cx = d.x * CELL + CELL / 2;
      const cy = d.y * CELL + CELL / 2;

      if (d.type === "building") {
        const color = buildingColors[d.color_idx ?? 0];
        const h = CELL * (d.height ?? 0.7);
        const w = CELL * 0.7;
        const bx = cx - w / 2, by = cy - h / 2;

        // Ombre portée
        g.roundRect(bx + 2, by + 4, w, h, 6).fill({ color: PALETTE.shadow, alpha: 0.35 });
        // Corps
        g.roundRect(bx, by, w, h, 6).fill(color);
        // Highlight haut/gauche (effet 3D doux)
        g.roundRect(bx + 2, by + 2, w - 4, 3, 2).fill({ color: PALETTE.buildingHighlight, alpha: 0.5 });
        g.roundRect(bx + 2, by + 2, 3, h - 4, 2).fill({ color: PALETTE.buildingHighlight, alpha: 0.3 });

        // Fenêtres en grille douce
        const windows = d.windows ?? 2;
        const winSize = 4;
        const winGap = 3;
        const winRows = Math.min(windows, Math.floor((h - 8) / (winSize + winGap)));
        for (let wi = 0; wi < winRows; wi++) {
          const wy = by + 6 + wi * (winSize + winGap);
          for (const xOffset of [4, w - 4 - winSize]) {
            g.roundRect(bx + xOffset, wy, winSize, winSize, 1).fill(PALETTE.window);
          }
        }
      } else if (d.type === "tree") {
        // Ombre
        g.ellipse(cx, cy + 8, 9, 3).fill({ color: PALETTE.shadow, alpha: 0.35 });
        // Tronc
        g.roundRect(cx - 2, cy + 2, 4, 8, 2).fill(PALETTE.treeTrunk);
        // Feuillage (cercles superposés pour dégradé)
        g.circle(cx, cy - 2, 10).fill(PALETTE.treeShadow);
        g.circle(cx - 1, cy - 3, 9).fill(PALETTE.treeTop);
        g.circle(cx - 3, cy - 5, 5).fill(PALETTE.treeTopLight);
      } else if (d.type === "small_tree") {
        g.ellipse(cx, cy + 5, 5, 2).fill({ color: PALETTE.shadow, alpha: 0.3 });
        g.roundRect(cx - 1, cy + 1, 2, 4, 1).fill(PALETTE.treeTrunk);
        g.circle(cx, cy - 1, 5).fill(PALETTE.treeTop);
        g.circle(cx - 1, cy - 2, 3).fill(PALETTE.treeTopLight);
      }
    }
    this.decoLayer.addChild(g);
  }

  // ── Landmarks : icônes propres ──────────────────────────────────────
  private drawLandmarks() {
    if (!this.staticData) return;
    this.landmarkLayer.removeChildren();
    const g = new Graphics();
    for (const lm of this.staticData.landmarks) {
      const cx = lm.x * CELL + CELL / 2;
      const cy = lm.y * CELL + CELL / 2;
      g.ellipse(cx, cy + 7, 8, 2.5).fill({ color: PALETTE.shadow, alpha: 0.3 });

      if (lm.shape === "fountain") {
        g.circle(cx, cy, 12).fill({ color: PALETTE.fountain, alpha: 0.25 });
        g.circle(cx, cy, 10).stroke({ width: 2, color: PALETTE.fountain });
        g.circle(cx, cy, 7).fill(PALETTE.fountainWater);
        g.circle(cx - 2, cy - 2, 2).fill({ color: 0xffffff, alpha: 0.7 });
      } else if (lm.shape === "statue") {
        g.roundRect(cx - 7, cy + 1, 14, 6, 2).fill(PALETTE.statueBase);
        g.circle(cx, cy - 3, 4.5).fill(PALETTE.statue);
        g.roundRect(cx - 4, cy + 1, 8, 3, 1).fill(PALETTE.statue);
      } else if (lm.shape === "bench") {
        g.roundRect(cx - 10, cy - 2, 20, 5, 2).fill(PALETTE.bench);
        g.roundRect(cx - 10, cy - 2, 20, 2, 2).fill({ color: PALETTE.benchLight, alpha: 0.7 });
        g.roundRect(cx - 8, cy + 3, 2, 4, 1).fill(PALETTE.treeTrunk);
        g.roundRect(cx + 6, cy + 3, 2, 4, 1).fill(PALETTE.treeTrunk);
      } else if (lm.shape === "lamp") {
        g.roundRect(cx - 1, cy - 6, 2, 14, 1).fill(PALETTE.buildingDark);
        // halo
        g.circle(cx, cy - 9, 8).fill({ color: PALETTE.lampGlow, alpha: 0.2 });
        g.circle(cx, cy - 9, 5).fill({ color: PALETTE.lampGlow, alpha: 0.35 });
        g.circle(cx, cy - 9, 3.5).fill(PALETTE.lamp);
      } else if (lm.shape === "sign") {
        g.roundRect(cx - 0.5, cy - 2, 1, 9, 0.5).fill(PALETTE.buildingDark);
        g.roundRect(cx - 6, cy - 8, 12, 8, 2).fill(PALETTE.sign);
        g.roundRect(cx - 6, cy - 8, 12, 2, 2).fill({ color: 0xffffff, alpha: 0.4 });
      }
    }
    this.landmarkLayer.addChild(g);
  }

  // ── Trail : trace douce qui s'estompe ───────────────────────────────
  private drawTrail() {
    if (!this.state) return;
    this.trailLayer.removeChildren();
    const g = new Graphics();
    const trail = this.state.trail;
    trail.forEach(([tx, ty], i) => {
      const alpha = 0.15 + (0.45 * i) / Math.max(trail.length, 1);
      const r = 2 + (3 * i) / Math.max(trail.length, 1);
      g.circle(tx * CELL + CELL / 2, ty * CELL + CELL / 2, r)
        .fill({ color: PALETTE.trail, alpha });
    });
    this.trailLayer.addChild(g);
  }

  // ── Objets : icônes lisses avec halo pulsant ────────────────────────
  private objectGraphics = new Graphics();
  private drawObjects() {
    if (!this.state) return;
    this.objectLayer.removeChildren();
    this.objectGraphics = new Graphics();
    this.objectLayer.addChild(this.objectGraphics);
    this.pulseObjects();
  }

  private pulseObjects() {
    if (!this.state || !this.initialized) return;
    const g = this.objectGraphics;
    g.clear();
    for (const obj of this.state.objects) {
      if (obj.collected) continue;
      const cx = obj.x * CELL + CELL / 2;
      const bob = Math.sin(this.clock * 2.2 + obj.x + obj.y) * 1.5;
      const cy = obj.y * CELL + CELL / 2 + bob;

      const color = this.objectColor(obj.shape);
      const haloAlpha = 0.18 + 0.12 * Math.sin(this.clock * 2.5 + obj.x);
      // double halo : large diffus + plus net
      g.circle(cx, cy, 16).fill({ color, alpha: haloAlpha * 0.5 });
      g.circle(cx, cy, 11).fill({ color, alpha: haloAlpha });

      // ombre douce
      g.ellipse(cx, cy + 9, 6, 2).fill({ color: PALETTE.shadow, alpha: 0.3 });

      this.drawObjectShape(g, obj.shape, cx, cy, color);
    }
  }

  private objectColor(shape: ObjectData["shape"]): number {
    switch (shape) {
      case "key": return PALETTE.key;
      case "diamond": return PALETTE.diamond;
      case "star": return PALETTE.star;
      case "coin": return PALETTE.coin;
      case "battery": return PALETTE.battery;
    }
  }

  private drawObjectShape(g: Graphics, shape: ObjectData["shape"], cx: number, cy: number, color: number) {
    const r = 6;
    if (shape === "key") {
      g.circle(cx - 3, cy - 1, 3.5).stroke({ width: 2.5, color });
      g.circle(cx - 3, cy - 1, 1.5).fill(color);
      g.roundRect(cx, cy - 1.5, 7, 3, 1).fill(color);
      g.roundRect(cx + 4, cy - 3.5, 2, 5, 1).fill(color);
      // brillance
      g.circle(cx - 4, cy - 2, 1).fill({ color: PALETTE.keyHighlight, alpha: 0.9 });
    } else if (shape === "diamond") {
      g.poly([cx, cy - r, cx + r, cy, cx, cy + r, cx - r, cy]).fill(color);
      g.poly([cx, cy - r, cx + r * 0.4, cy - r * 0.3, cx, cy + r * 0.2])
        .fill({ color: PALETTE.diamondHighlight, alpha: 0.7 });
      g.poly([cx, cy - r, cx + r, cy, cx, cy + r, cx - r, cy])
        .stroke({ width: 1.5, color: 0xffffff, alpha: 0.6 });
    } else if (shape === "star") {
      this.drawStar(g, cx, cy, r, color);
      g.circle(cx - 1, cy - 1, 1.5).fill({ color: PALETTE.starHighlight, alpha: 0.9 });
    } else if (shape === "coin") {
      g.circle(cx, cy, r).fill(color);
      g.circle(cx, cy, r - 1).stroke({ width: 1, color: PALETTE.coinHighlight, alpha: 0.7 });
      g.circle(cx - 1.5, cy - 1.5, 1.5).fill({ color: PALETTE.coinHighlight, alpha: 0.9 });
    } else if (shape === "battery") {
      g.roundRect(cx - 3.5, cy - r, 7, r * 2, 1).fill(color);
      g.roundRect(cx - 1.5, cy - r - 1.5, 3, 2, 0.5).fill(color);
      // indicateur de charge
      g.roundRect(cx - 2.5, cy - r + 1.5, 5, 1.5, 0.5).fill({ color: PALETTE.batteryHighlight, alpha: 0.9 });
    }
  }

  private drawStar(g: Graphics, cx: number, cy: number, r: number, color: number) {
    const points: number[] = [];
    const innerR = r * 0.45;
    for (let i = 0; i < 10; i++) {
      const angle = -Math.PI / 2 + (i * Math.PI) / 5;
      const radius = i % 2 === 0 ? r : innerR;
      points.push(cx + Math.cos(angle) * radius, cy + Math.sin(angle) * radius);
    }
    g.poly(points).fill(color);
  }

  // ── Robot : design moderne, snap case par case avec petit pop ──────
  private drawRobot() {
    if (!this.state) return;
    const cx = this.robotPos.x * CELL + CELL / 2;
    const cy = this.robotPos.y * CELL + CELL / 2;
    const angle = (this.robotPos.dir - 1) * (Math.PI / 2);

    // Pop d'arrivée : sinusoïde courte, 0→pic→0
    const popScale = 1 + 0.18 * Math.sin(this.arrivePulse * Math.PI);
    const wobble = Math.sin(this.clock * 4) * 0.5; // léger flottement
    const bodyR = 13 * popScale;

    // Ombre dynamique
    this.robotShadow.clear();
    this.robotShadow.ellipse(cx, cy + 12 - wobble * 0.5, 10 * popScale, 3.5)
      .fill({ color: PALETTE.shadow, alpha: 0.45 });

    const g = this.robotG;
    g.clear();

    const ry = cy + wobble; // léger flottement vertical

    // Halo diffus si agent actif
    if (this.state.agent.active) {
      const ringR = 18 + 2 * Math.sin(this.clock * 3);
      g.circle(cx, ry, ringR).fill({ color: PALETTE.highlight, alpha: 0.18 });
      g.circle(cx, ry, ringR).stroke({ width: 1.5, color: PALETTE.highlight, alpha: 0.7 });
    }

    // Corps : cercle avec dégradé simulé (3 cercles concentriques)
    g.circle(cx, ry, bodyR).fill(PALETTE.robotBodyDark);
    g.circle(cx, ry, bodyR - 1.5).fill(PALETTE.robotBody);
    g.circle(cx - bodyR * 0.35, ry - bodyR * 0.4, bodyR * 0.45)
      .fill({ color: PALETTE.robotBodyLight, alpha: 0.65 });
    // outline subtil
    g.circle(cx, ry, bodyR).stroke({ width: 1.5, color: PALETTE.robotBodyDark, alpha: 0.9 });

    // Visor directionnel — losange aplati façon casque
    const visorLen = bodyR * 0.95;
    const visorWidth = bodyR * 0.55;
    const tipX = cx + Math.cos(angle) * visorLen;
    const tipY = ry + Math.sin(angle) * visorLen;
    const perp = angle + Math.PI / 2;
    const sx1 = cx + Math.cos(angle) * (visorLen * 0.35) + Math.cos(perp) * visorWidth;
    const sy1 = ry + Math.sin(angle) * (visorLen * 0.35) + Math.sin(perp) * visorWidth;
    const sx2 = cx + Math.cos(angle) * (visorLen * 0.35) - Math.cos(perp) * visorWidth;
    const sy2 = ry + Math.sin(angle) * (visorLen * 0.35) - Math.sin(perp) * visorWidth;
    g.poly([tipX, tipY, sx1, sy1, sx2, sy2]).fill(PALETTE.robotHead);
    g.poly([tipX, tipY, sx1, sy1, sx2, sy2])
      .stroke({ width: 1, color: PALETTE.robotHeadLight, alpha: 0.7 });

    // Yeux
    for (const side of [-1, 1]) {
      const ex = cx + Math.cos(angle) * 1 + Math.cos(perp) * 4 * side;
      const ey = ry + Math.sin(angle) * 1 + Math.sin(perp) * 4 * side;
      g.circle(ex, ey, 2.2).fill(PALETTE.robotEye);
      g.circle(ex + Math.cos(angle) * 0.8, ey + Math.sin(angle) * 0.8, 1).fill(PALETTE.robotPupil);
    }

    // Antenne (arrière)
    const baseX = cx - Math.cos(angle) * (bodyR * 0.5);
    const baseY = ry - Math.sin(angle) * (bodyR * 0.5);
    const tipAx = baseX - Math.cos(angle) * 7;
    const tipAy = baseY - Math.sin(angle) * 7;
    g.moveTo(baseX, baseY).lineTo(tipAx, tipAy)
      .stroke({ width: 1.5, color: PALETTE.antenna });
    // halo lumineux sur la pointe
    g.circle(tipAx, tipAy, 3.5).fill({ color: PALETTE.antennaTip, alpha: 0.4 });
    g.circle(tipAx, tipAy, 2).fill(PALETTE.antennaTip);
  }

  // ── Particles ──────────────────────────────────────────────────────
  private spawnGrabBurst(ev: GrabEvent) {
    if (ev.x === undefined || ev.y === undefined) return;
    const cx = ev.x * CELL + CELL / 2;
    const cy = ev.y * CELL + CELL / 2;
    for (let i = 0; i < 14; i++) {
      const angle = (Math.PI * 2 * i) / 14;
      const speed = 30 + Math.random() * 50;
      this.particles.push({
        x: cx, y: cy,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed,
        life: 0.7, maxLife: 0.7,
        color: PALETTE.grabGlow, size: 3,
      });
    }
  }

  private spawnCollectBurst(obj: ObjectData) {
    const cx = obj.x * CELL + CELL / 2;
    const cy = obj.y * CELL + CELL / 2;
    const color = this.objectColor(obj.shape);
    for (let i = 0; i < 22; i++) {
      const angle = Math.random() * Math.PI * 2;
      const speed = 25 + Math.random() * 50;
      this.particles.push({
        x: cx, y: cy,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed - 20,
        life: 0.9, maxLife: 0.9,
        color, size: 2.5,
      });
    }
  }

  private fxGraphics = new Graphics();
  private drawParticles(dt: number) {
    if (!this.fxLayer.children.includes(this.fxGraphics)) {
      this.fxLayer.addChild(this.fxGraphics);
    }
    const g = this.fxGraphics;
    g.clear();
    this.particles = this.particles.filter((p) => {
      p.life -= dt;
      if (p.life <= 0) return false;
      p.x += p.vx * dt;
      p.y += p.vy * dt;
      p.vy += 50 * dt;
      const alpha = p.life / p.maxLife;
      const r = p.size * (0.5 + alpha * 0.5);
      // halo flou + dot net
      g.circle(p.x, p.y, r * 2).fill({ color: p.color, alpha: alpha * 0.3 });
      g.circle(p.x, p.y, r).fill({ color: p.color, alpha });
      return true;
    });
  }

  // ── Fog ────────────────────────────────────────────────────────────
  private drawFog() {
    if (!this.state || !this.staticData) return;
    this.fogLayer.removeChildren();
    if (!this.state.fog_visited) return;
    const visited = new Set(this.state.fog_visited.map(([x, y]) => `${x},${y}`));
    const g = new Graphics();
    for (let x = 0; x < this.staticData.grid_size; x++) {
      for (let y = 0; y < this.staticData.grid_size; y++) {
        if (!visited.has(`${x},${y}`)) {
          g.roundRect(x * CELL + 1, y * CELL + 1, CELL - 2, CELL - 2, 6)
            .fill({ color: PALETTE.fog, alpha: 0.6 });
        }
      }
    }
    this.fogLayer.addChild(g);
  }

  destroy() {
    this.destroyed = true;
    if (this.initialized) {
      try { this.app.destroy(true, { children: true }); } catch { /* ignore */ }
      this.initialized = false;
    }
  }
}

export const GAME_WIDTH = GRID * CELL;
export const GAME_HEIGHT = GRID * CELL;
