import { Application, Container, Graphics, Ticker } from "pixi.js";
import { PALETTE } from "./colors";
import type { StaticPayload, StatePayload, ObjectData, GrabEvent } from "../net/types";

const CELL = 32;          // taille tuile en px (rendu)
const SCALE = 2;          // scale visuel (pixel art @2x)

interface Particle {
  x: number; y: number; vx: number; vy: number;
  life: number; maxLife: number; color: number; size: number;
}

export class GameRenderer {
  app: Application;
  private bgLayer = new Container();
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

  // Animation state
  private displayPos = { x: 5, y: 5, dir: 0 };
  private targetPos = { x: 5, y: 5, dir: 0 };
  private animT = 1;             // 0→1 interpolation
  private particles: Particle[] = [];
  private clock = 0;

  // Map des objets pour suivre quels sont collectés (pour fx)
  private knownObjects = new Map<number, ObjectData>();

  constructor(canvas: HTMLCanvasElement) {
    this.app = new Application();
    this.init(canvas);
  }

  private async init(canvas: HTMLCanvasElement) {
    await this.app.init({
      canvas,
      width: 11 * CELL * SCALE,
      height: 11 * CELL * SCALE,
      backgroundColor: 0x0a0a14,
      antialias: false,
      roundPixels: true,
    });
    const root = new Container();
    root.scale.set(SCALE);
    root.addChild(
      this.bgLayer,
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
  }

  resize(width: number, height: number) {
    this.app.renderer.resize(width, height);
  }

  get gridPx() {
    return 11 * CELL * SCALE;
  }

  setStatic(payload: StaticPayload) {
    this.staticData = payload;
    this.drawBackground();
    this.drawDecorations();
    this.drawLandmarks();
  }

  setState(state: StatePayload) {
    // Détecter ramassages → particles
    if (state.grab_event?.success && state.grab_event.x !== undefined && state.grab_event.y !== undefined) {
      this.spawnGrabBurst(state.grab_event);
    }

    // Snapshot anciens objets pour anim de disparition
    for (const o of state.objects) {
      const prev = this.knownObjects.get(o.id);
      if (prev && !prev.collected && o.collected) {
        this.spawnCollectBurst(o);
      }
      this.knownObjects.set(o.id, o);
    }

    // Anim du robot
    if (
      this.state &&
      (this.state.robot.x !== state.robot.x || this.state.robot.y !== state.robot.y || this.state.robot.dir !== state.robot.dir)
    ) {
      this.displayPos = { ...this.displayPos };
      this.targetPos = { x: state.robot.x, y: state.robot.y, dir: state.robot.dir };
      this.animT = 0;
    } else if (!this.state) {
      this.displayPos = { x: state.robot.x, y: state.robot.y, dir: state.robot.dir };
      this.targetPos = { ...this.displayPos };
      this.animT = 1;
    }

    this.state = state;
    this.drawTrail();
    this.drawObjects();
    this.drawFog();
  }

  private tick(t: Ticker) {
    this.clock += t.deltaMS / 1000;
    if (this.animT < 1) {
      this.animT = Math.min(1, this.animT + t.deltaMS / 150);
    }
    this.drawRobot();
    this.drawParticles(t.deltaMS / 1000);
    this.pulseObjects();
  }

  // ── Background ──────────────────────────────────────
  private drawBackground() {
    if (!this.staticData) return;
    this.bgLayer.removeChildren();
    const g = new Graphics();
    const { grid_size, map } = this.staticData;
    for (let x = 0; x < grid_size; x++) {
      for (let y = 0; y < grid_size; y++) {
        const cell = map[x][y];
        const px = x * CELL, py = y * CELL;
        if (cell === 1) {
          g.rect(px, py, CELL, CELL).fill(PALETTE.road);
          this.drawRoadMarkings(g, x, y, px, py);
        } else if (cell === 2) {
          g.rect(px, py, CELL, CELL).fill(PALETTE.sidewalk);
          // Pavés
          for (let i = 0; i < CELL; i += 4) {
            g.rect(px + i, py, 1, CELL).fill(PALETTE.sidewalkLight);
          }
        } else if (cell === 3) {
          g.rect(px, py, CELL, CELL).fill(PALETTE.grass);
          if ((x + y) % 2 === 0) {
            g.rect(px + 4, py + 4, CELL - 8, CELL - 8).fill(PALETTE.grassDark);
          }
        }
      }
    }
    this.bgLayer.addChild(g);
  }

  private drawRoadMarkings(g: Graphics, gx: number, gy: number, px: number, py: number) {
    const ROAD_COLS = new Set([2, 5, 8]);
    const ROAD_ROWS = new Set([2, 5, 8]);
    if (ROAD_ROWS.has(gy)) {
      for (let i = 0; i < CELL; i += 6) {
        g.rect(px + i, py + CELL / 2 - 1, 3, 2).fill(PALETTE.roadLine);
      }
    }
    if (ROAD_COLS.has(gx)) {
      for (let i = 0; i < CELL; i += 6) {
        g.rect(px + CELL / 2 - 1, py + i, 2, 3).fill(PALETTE.roadLine);
      }
    }
  }

  // ── Décorations ────────────────────────────────────
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
        const h = Math.floor(CELL * (d.height ?? 0.7));
        const w = Math.floor(CELL * 0.7);
        const bx = cx - w / 2, by = cy - h / 2;
        g.rect(bx, by, w, h).fill(color).stroke({ width: 1, color: PALETTE.buildingDark });
        const windows = d.windows ?? 2;
        for (let wi = 0; wi < windows; wi++) {
          const wy = by + 3 + wi * 5;
          if (wy + 3 > by + h) break;
          g.rect(bx + 2, wy, 3, 3).fill(PALETTE.window);
          g.rect(bx + w - 5, wy, 3, 3).fill(PALETTE.window);
        }
      } else if (d.type === "tree") {
        g.rect(cx - 1, cy, 3, 7).fill(PALETTE.treeTrunk);
        g.circle(cx, cy - 2, 7).fill(PALETTE.treeTop);
        g.circle(cx - 2, cy - 4, 4).fill(PALETTE.treeTopLight);
      } else if (d.type === "small_tree") {
        g.rect(cx - 1, cy + 1, 2, 4).fill(PALETTE.treeTrunk);
        g.circle(cx, cy, 4).fill(PALETTE.treeTopLight);
      }
    }
    this.decoLayer.addChild(g);
  }

  // ── Landmarks ──────────────────────────────────────
  private drawLandmarks() {
    if (!this.staticData) return;
    this.landmarkLayer.removeChildren();
    const g = new Graphics();
    for (const lm of this.staticData.landmarks) {
      const cx = lm.x * CELL + CELL / 2;
      const cy = lm.y * CELL + CELL / 2;
      if (lm.shape === "fountain") {
        g.circle(cx, cy, 10).stroke({ width: 2, color: PALETTE.fountain });
        g.circle(cx, cy, 6).fill(PALETTE.fountainWater);
      } else if (lm.shape === "statue") {
        g.rect(cx - 5, cy + 2, 10, 5).fill(PALETTE.statueBase);
        g.circle(cx, cy - 2, 4).fill(PALETTE.statue);
        g.rect(cx - 4, cy + 1, 8, 3).fill(PALETTE.statue);
      } else if (lm.shape === "bench") {
        g.rect(cx - 8, cy - 2, 16, 4).fill(PALETTE.bench);
        g.rect(cx - 7, cy + 2, 2, 3).fill(PALETTE.treeTrunk);
        g.rect(cx + 5, cy + 2, 2, 3).fill(PALETTE.treeTrunk);
      } else if (lm.shape === "lamp") {
        g.rect(cx - 1, cy - 6, 2, 12).fill(PALETTE.buildingDark);
        g.circle(cx, cy - 8, 3).fill(PALETTE.lamp);
        g.circle(cx, cy - 8, 5).fill({ color: PALETTE.lamp, alpha: 0.3 });
      } else if (lm.shape === "sign") {
        g.rect(cx, cy - 2, 1, 8).fill(PALETTE.buildingDark);
        g.rect(cx - 5, cy - 7, 10, 7).fill(PALETTE.sign).stroke({ width: 1, color: 0xffffff });
      }
    }
    this.landmarkLayer.addChild(g);
  }

  // ── Trail ──────────────────────────────────────────
  private drawTrail() {
    if (!this.state) return;
    this.trailLayer.removeChildren();
    const g = new Graphics();
    const trail = this.state.trail;
    trail.forEach(([tx, ty], i) => {
      const alpha = 0.3 + (0.5 * i) / Math.max(trail.length, 1);
      g.circle(tx * CELL + CELL / 2, ty * CELL + CELL / 2, 2)
        .fill({ color: PALETTE.trail, alpha });
    });
    this.trailLayer.addChild(g);
  }

  // ── Objets ─────────────────────────────────────────
  private objectGraphics = new Graphics();
  private drawObjects() {
    if (!this.state) return;
    this.objectLayer.removeChildren();
    this.objectGraphics = new Graphics();
    this.objectLayer.addChild(this.objectGraphics);
    this.pulseObjects();
  }

  private pulseObjects() {
    if (!this.state) return;
    const g = this.objectGraphics;
    g.clear();
    for (const obj of this.state.objects) {
      if (obj.collected) continue;
      const cx = obj.x * CELL + CELL / 2;
      const bob = Math.sin(this.clock * 2.5 + obj.x + obj.y) * 1.5;
      const cy = obj.y * CELL + CELL / 2 + bob;

      const color = this.objectColor(obj.shape);
      // Halo pulsant
      const haloAlpha = 0.2 + 0.15 * Math.sin(this.clock * 3 + obj.x);
      g.circle(cx, cy, 9).fill({ color, alpha: haloAlpha });

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
    const r = 5;
    if (shape === "key") {
      g.circle(cx - 2, cy - 1, 3).stroke({ width: 2, color });
      g.rect(cx, cy - 1, 5, 2).fill(color);
      g.rect(cx + 4, cy - 3, 2, 4).fill(color);
    } else if (shape === "diamond") {
      g.poly([cx, cy - r, cx + r, cy, cx, cy + r, cx - r, cy]).fill(color);
      g.poly([cx, cy - r, cx + r, cy, cx, cy + r, cx - r, cy]).stroke({ width: 1, color: 0xffffff });
    } else if (shape === "star") {
      this.drawStar(g, cx, cy, r, color);
    } else if (shape === "coin") {
      g.circle(cx, cy, r).fill(color);
      g.circle(cx, cy, r - 2).stroke({ width: 1, color: 0xffe070 });
    } else if (shape === "battery") {
      g.rect(cx - 3, cy - r, 6, r * 2).fill(color).stroke({ width: 1, color: PALETTE.buildingDark });
      g.rect(cx - 1, cy - r - 2, 2, 2).fill(color);
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

  // ── Robot ──────────────────────────────────────────
  private drawRobot() {
    if (!this.state) return;
    // Easing
    const t = this.easeOutCubic(this.animT);
    const x = this.lerp(this.displayPos.x, this.targetPos.x, t);
    const y = this.lerp(this.displayPos.y, this.targetPos.y, t);
    // Rotation : prendre le chemin le plus court
    const dirDelta = ((this.targetPos.dir - this.displayPos.dir + 6) % 4) - 2;
    const dirInterp = this.displayPos.dir + dirDelta * t;

    if (this.animT >= 1) {
      this.displayPos = { x: this.targetPos.x, y: this.targetPos.y, dir: this.targetPos.dir };
    }

    const cx = x * CELL + CELL / 2;
    const cy = y * CELL + CELL / 2;
    const angle = (dirInterp - 1) * (Math.PI / 2); // dir 0=N (-90°), 1=E (0°), 2=S (90°), 3=W (180°)

    // Ombre
    this.robotShadow.clear();
    this.robotShadow.ellipse(cx, cy + 6, 9, 3).fill({ color: 0x000000, alpha: 0.4 });

    const g = this.robotG;
    g.clear();
    // Corps
    g.circle(cx, cy, 9).fill(PALETTE.robotBody).stroke({ width: 1, color: PALETTE.robotBodyDark });
    // Triangle directionnel
    const tipX = cx + Math.cos(angle) * 11;
    const tipY = cy + Math.sin(angle) * 11;
    const leftX = cx + Math.cos(angle + 2.5) * 7;
    const leftY = cy + Math.sin(angle + 2.5) * 7;
    const rightX = cx + Math.cos(angle - 2.5) * 7;
    const rightY = cy + Math.sin(angle - 2.5) * 7;
    g.poly([tipX, tipY, leftX, leftY, rightX, rightY]).fill(PALETTE.robotHead);
    // Yeux
    const perp = angle + Math.PI / 2;
    for (const side of [-1, 1]) {
      const ex = cx + Math.cos(angle) * 2 + Math.cos(perp) * 3 * side;
      const ey = cy + Math.sin(angle) * 2 + Math.sin(perp) * 3 * side;
      g.circle(ex, ey, 1.6).fill(PALETTE.robotEye);
      g.circle(ex + Math.cos(angle) * 0.6, ey + Math.sin(angle) * 0.6, 0.7).fill(PALETTE.robotPupil);
    }
    // Antenne
    const ax = cx - Math.cos(angle) * 4;
    const ay = cy - Math.sin(angle) * 4;
    const atx = ax - Math.cos(angle) * 5;
    const aty = ay - Math.sin(angle) * 5;
    g.moveTo(ax, ay).lineTo(atx, aty).stroke({ width: 1, color: PALETTE.antenna });
    g.circle(atx, aty, 1.5).fill(PALETTE.robotHead);

    // Halo si agent actif
    if (this.state.agent.active) {
      const haloPulse = 0.3 + 0.2 * Math.sin(this.clock * 4);
      g.circle(cx, cy, 14).stroke({ width: 1, color: PALETTE.highlight, alpha: haloPulse });
    }
  }

  // ── Particles ──────────────────────────────────────
  private spawnGrabBurst(ev: GrabEvent) {
    if (ev.x === undefined || ev.y === undefined) return;
    const cx = ev.x * CELL + CELL / 2;
    const cy = ev.y * CELL + CELL / 2;
    for (let i = 0; i < 12; i++) {
      const angle = (Math.PI * 2 * i) / 12;
      const speed = 20 + Math.random() * 30;
      this.particles.push({
        x: cx, y: cy,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed,
        life: 0.6, maxLife: 0.6,
        color: PALETTE.grabGlow, size: 2,
      });
    }
  }

  private spawnCollectBurst(obj: ObjectData) {
    const cx = obj.x * CELL + CELL / 2;
    const cy = obj.y * CELL + CELL / 2;
    const color = this.objectColor(obj.shape);
    for (let i = 0; i < 16; i++) {
      const angle = Math.random() * Math.PI * 2;
      const speed = 15 + Math.random() * 25;
      this.particles.push({
        x: cx, y: cy,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed - 10,
        life: 0.8, maxLife: 0.8,
        color, size: 1.5,
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
      p.vy += 30 * dt; // gravité
      const alpha = p.life / p.maxLife;
      g.rect(p.x - p.size / 2, p.y - p.size / 2, p.size, p.size)
        .fill({ color: p.color, alpha });
      return true;
    });
  }

  // ── Fog ────────────────────────────────────────────
  private drawFog() {
    if (!this.state || !this.staticData) return;
    this.fogLayer.removeChildren();
    if (!this.state.fog_visited) return;
    const visited = new Set(this.state.fog_visited.map(([x, y]) => `${x},${y}`));
    const g = new Graphics();
    for (let x = 0; x < this.staticData.grid_size; x++) {
      for (let y = 0; y < this.staticData.grid_size; y++) {
        if (!visited.has(`${x},${y}`)) {
          g.rect(x * CELL, y * CELL, CELL, CELL).fill({ color: PALETTE.fog, alpha: 0.55 });
        }
      }
    }
    this.fogLayer.addChild(g);
  }

  private lerp(a: number, b: number, t: number) { return a + (b - a) * t; }
  private easeOutCubic(t: number) { return 1 - Math.pow(1 - t, 3); }

  destroy() {
    this.app.destroy(true, { children: true });
  }
}

export const GAME_WIDTH = 11 * CELL * SCALE;
export const GAME_HEIGHT = 11 * CELL * SCALE;
