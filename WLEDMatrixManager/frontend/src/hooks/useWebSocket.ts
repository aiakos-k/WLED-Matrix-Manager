import { useEffect, useRef, useCallback, useState } from "react";

// Always compute WS URL from the current location so it works
// both in HA ingress (/api/hassio_ingress/TOKEN/ws) and local dev.
const WS_URL = `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}${window.location.pathname.replace(/\/$/, "")}/ws`;

type MessageHandler = (data: unknown) => void;

export function useWebSocket(onMessage?: MessageHandler) {
  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const reconnectRef = useRef(0);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      reconnectRef.current = 0;
    };
    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        onMessage?.(data);
      } catch {
        /* ignore */
      }
    };
    ws.onerror = () => setConnected(false);
    ws.onclose = () => {
      setConnected(false);
      if (reconnectRef.current < 5) {
        const delay = Math.min(1000 * 2 ** reconnectRef.current, 30000);
        reconnectRef.current++;
        setTimeout(connect, delay);
      }
    };
  }, [onMessage]);

  useEffect(() => {
    connect();
    return () => {
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [connect]);

  const send = useCallback((data: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  return { connected, send };
}
