export type Direction = 0 | 1 | 2 | 3;

export interface MapDecoration {
  x: number;
  y: number;
  type: "building" | "tree" | "small_tree";
  color_idx?: number;
  height?: number;
  windows?: number;
}

export interface LandmarkData {
  name: string;
  shape: "fountain" | "statue" | "bench" | "lamp" | "sign";
  x: number;
  y: number;
}

export interface StaticPayload {
  grid_size: number;
  map: number[][];
  decorations: MapDecoration[];
  landmarks: LandmarkData[];
}

export interface RobotData {
  x: number;
  y: number;
  dir: Direction;
  dir_name: string;
}

export interface ObjectData {
  id: number;
  type: string;
  shape: "key" | "diamond" | "star" | "coin" | "battery";
  x: number;
  y: number;
  collected: boolean;
}

export interface AgentData {
  active: boolean;
  status: string;
  target_type: string;
  collected: number;
  max_collect: number;
  mode: string;
}

export interface GrabEvent {
  success: boolean;
  name?: string;
  x?: number;
  y?: number;
}

export interface StatePayload {
  robot: RobotData;
  objects: ObjectData[];
  trail: number[][];
  inventory: Record<string, number>;
  inventory_total: number;
  objects_total: number;
  fog_visited: number[][] | null;
  grab_event: GrabEvent | null;
  nearby: string[];
  agent: AgentData;
}

export type ServerMessage =
  | { type: "static"; payload: StaticPayload }
  | { type: "state"; payload: StatePayload }
  | { type: "voice"; text: string; recognized: string | null }
  | { type: "error"; message: string };

export type ClientMessage =
  | { type: "action"; action: "forward" | "left" | "right" | "grab" }
  | { type: "reset" }
  | { type: "agent"; target_type: string; count: number }
  | { type: "agent_cancel" }
  | { type: "flush_audio" };
