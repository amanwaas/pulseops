import { useEffect, useRef, useState, useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';

export type WebSocketConnectionState = 'DISCONNECTED' | 'CONNECTING' | 'CONNECTED' | 'RECONNECTING';

export interface LiveEvent {
  type: string;
  data: any;
  timestamp: number;
}

export function useWebSocket() {
  const queryClient = useQueryClient();
  const [connectionState, setConnectionState] = useState<WebSocketConnectionState>('DISCONNECTED');
  const [lastEvent, setLastEvent] = useState<LiveEvent | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const pingIntervalRef = useRef<number | null>(null);
  const connectionStateRef = useRef<WebSocketConnectionState>('DISCONNECTED');
  const isUnmountedRef = useRef<boolean>(false);

  // Update state helper to keep ref and React state synchronized
  const transitionTo = useCallback((nextState: WebSocketConnectionState) => {
    connectionStateRef.current = nextState;
    if (!isUnmountedRef.current) {
      setConnectionState(nextState);
    }
  }, []);

  const cleanupTimers = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = null;
    }
  }, []);

  const connect = useCallback(() => {
    if (isUnmountedRef.current) return;

    // State machine guard: Do not create duplicate connections if already active or in handshake
    if (
      wsRef.current &&
      (wsRef.current.readyState === WebSocket.CONNECTING || wsRef.current.readyState === WebSocket.OPEN)
    ) {
      return;
    }

    cleanupTimers();
    transitionTo('CONNECTING');

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const wsUrl = import.meta.env.VITE_WS_URL || `${protocol}//${host}/ws/live`;

    try {
      const socket = new WebSocket(wsUrl);
      wsRef.current = socket;

      socket.onopen = () => {
        if (isUnmountedRef.current) {
          socket.close();
          return;
        }

        transitionTo('CONNECTED');

        // Start ping heartbeat every 30s
        pingIntervalRef.current = window.setInterval(() => {
          if (socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({ type: 'ping' }));
          }
        }, 30000);
      };

      socket.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          const liveEvent: LiveEvent = {
            type: payload.type,
            data: payload.data,
            timestamp: Date.now(),
          };
          setLastEvent(liveEvent);

          // Real-time React Query Cache Invalidation
          if (payload.type === 'deployment_created' || payload.type === 'deployment_updated') {
            queryClient.invalidateQueries({ queryKey: ['overview-cards'] });
            queryClient.invalidateQueries({ queryKey: ['deployments'] });
            queryClient.invalidateQueries({ queryKey: ['deployment-stats'] });
          } else if (payload.type === 'health_ping') {
            queryClient.invalidateQueries({ queryKey: ['overview-cards'] });
            queryClient.invalidateQueries({ queryKey: ['health-targets'] });
            queryClient.invalidateQueries({ queryKey: ['target-timeline'] });
          } else if (payload.type === 'incident_opened' || payload.type === 'incident_resolved') {
            queryClient.invalidateQueries({ queryKey: ['overview-cards'] });
            queryClient.invalidateQueries({ queryKey: ['incidents'] });
            queryClient.invalidateQueries({ queryKey: ['health-targets'] });
          }
        } catch {
          // Ignore invalid frames
        }
      };

      socket.onclose = () => {
        if (isUnmountedRef.current) return;
        cleanupTimers();
        transitionTo('RECONNECTING');

        // Reconnect after 3-second backoff
        reconnectTimeoutRef.current = window.setTimeout(() => {
          connect();
        }, 3000);
      };

      socket.onerror = () => {
        // Trigger close to route through state machine
        if (socket.readyState !== WebSocket.CLOSED) {
          socket.close();
        }
      };
    } catch {
      if (!isUnmountedRef.current) {
        transitionTo('RECONNECTING');
        reconnectTimeoutRef.current = window.setTimeout(() => {
          connect();
        }, 5000);
      }
    }
  }, [queryClient, transitionTo, cleanupTimers]);

  useEffect(() => {
    isUnmountedRef.current = false;
    connect();

    return () => {
      isUnmountedRef.current = true;
      transitionTo('DISCONNECTED');
      cleanupTimers();
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect, cleanupTimers, transitionTo]);

  return {
    connectionState,
    isConnected: connectionState === 'CONNECTED',
    lastEvent,
    reconnect: connect,
  };
}
