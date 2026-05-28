// Palette moderne, inspirée des dashboards web (Linear / Vercel) — indigo, cyan,
// emerald sur fond slate profond. Plus de pixel-art : couleurs douces avec
// dégradés et highlights subtils.
export const PALETTE = {
  // Sols
  grass: 0x1f3a2e,
  grassLight: 0x2a4d3d,
  grassDark: 0x16291f,
  road: 0x12141e,
  roadLine: 0x8b5cf6,
  sidewalk: 0x252839,
  sidewalkLight: 0x2f334a,
  gridLine: 0x1c1f2e,

  // Bâtiments
  building1: 0x3b4163,
  building2: 0x4a3f6b,
  building3: 0x3f5470,
  buildingDark: 0x171928,
  buildingHighlight: 0x5a6088,
  window: 0xfbbf24,
  windowDark: 0x78350f,

  // Arbres
  treeTrunk: 0x44291b,
  treeTop: 0x10b981,
  treeTopLight: 0x34d399,
  treeShadow: 0x064e3b,

  // Robot
  robotBody: 0x22d3ee,
  robotBodyDark: 0x0e7490,
  robotBodyLight: 0x67e8f9,
  robotHead: 0xfb7185,
  robotHeadLight: 0xfecdd3,
  robotEye: 0xffffff,
  robotPupil: 0x0f172a,
  antenna: 0xa78bfa,
  antennaTip: 0xf472b6,

  // Objets
  key: 0xfbbf24,
  keyHighlight: 0xfde68a,
  diamond: 0x22d3ee,
  diamondHighlight: 0xa5f3fc,
  star: 0xfde047,
  starHighlight: 0xfef9c3,
  coin: 0xf59e0b,
  coinHighlight: 0xfcd34d,
  battery: 0x34d399,
  batteryHighlight: 0x6ee7b7,

  // Landmarks
  fountain: 0x60a5fa,
  fountainWater: 0xbfdbfe,
  statue: 0xd6d3d1,
  statueBase: 0x78716c,
  bench: 0x92400e,
  benchLight: 0xb45309,
  lamp: 0xfde047,
  lampGlow: 0xfffbeb,
  sign: 0xf43f5e,

  // FX
  trail: 0x22d3ee,
  grabGlow: 0xfde047,
  fog: 0x0b0d17,
  highlight: 0xa78bfa,
  shadow: 0x000000,
} as const;
