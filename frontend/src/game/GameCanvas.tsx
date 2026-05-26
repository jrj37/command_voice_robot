import { useEffect, useRef } from "react";
import { GameRenderer, GAME_WIDTH, GAME_HEIGHT } from "./renderer";
import type { StaticPayload, StatePayload } from "../net/types";

interface Props {
  staticData: StaticPayload | null;
  state: StatePayload | null;
}

export function GameCanvas({ staticData, state }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rendererRef = useRef<GameRenderer | null>(null);

  useEffect(() => {
    if (!canvasRef.current) return;
    const r = new GameRenderer(canvasRef.current);
    rendererRef.current = r;
    return () => {
      rendererRef.current = null;
      r.destroy();
    };
  }, []);

  useEffect(() => {
    if (staticData) rendererRef.current?.setStatic(staticData);
  }, [staticData]);

  useEffect(() => {
    if (state) rendererRef.current?.setState(state);
  }, [state]);

  return <canvas ref={canvasRef} width={GAME_WIDTH} height={GAME_HEIGHT} />;
}
