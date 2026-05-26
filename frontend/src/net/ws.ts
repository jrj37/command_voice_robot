import type { ClientMessage, ServerMessage } from "./types";

export class GameSocket {
  private ws: WebSocket | null = null;
  private url: string;
  private reconnectTimer: number | null = null;
  private reconnectDelay = 1000;
  private listeners = new Set<(msg: ServerMessage) => void>();
  private statusListeners = new Set<(connected: boolean) => void>();

  constructor(url?: string) {
    if (url) {
      this.url = url;
    } else {
      const proto = location.protocol === "https:" ? "wss:" : "ws:";
      this.url = `${proto}//${location.host}/ws`;
    }
  }

  connect() {
    if (this.ws) return;
    this.ws = new WebSocket(this.url);
    this.ws.binaryType = "arraybuffer";

    this.ws.onopen = () => {
      this.reconnectDelay = 1000;
      this.statusListeners.forEach((l) => l(true));
    };

    this.ws.onmessage = (ev) => {
      if (typeof ev.data !== "string") return;
      try {
        const msg = JSON.parse(ev.data) as ServerMessage;
        this.listeners.forEach((l) => l(msg));
      } catch {
        // ignore
      }
    };

    this.ws.onclose = () => {
      this.ws = null;
      this.statusListeners.forEach((l) => l(false));
      this.scheduleReconnect();
    };

    this.ws.onerror = () => {
      // onclose will follow
    };
  }

  private scheduleReconnect() {
    if (this.reconnectTimer != null) return;
    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectTimer = null;
      this.reconnectDelay = Math.min(this.reconnectDelay * 2, 5000);
      this.connect();
    }, this.reconnectDelay);
  }

  send(msg: ClientMessage) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg));
    }
  }

  sendBinary(data: ArrayBuffer) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(data);
    }
  }

  onMessage(cb: (msg: ServerMessage) => void) {
    this.listeners.add(cb);
    return () => this.listeners.delete(cb);
  }

  onStatus(cb: (connected: boolean) => void) {
    this.statusListeners.add(cb);
    return () => this.statusListeners.delete(cb);
  }

  close() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.ws?.close();
    this.ws = null;
  }
}
