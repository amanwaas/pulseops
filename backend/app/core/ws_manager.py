import asyncio
import json
import logging
from typing import List, Dict, Any, Set
from fastapi import WebSocket

logger = logging.getLogger("pulseops.websocket")


class ConnectionManager:
    """
    Manages active WebSocket connections and SSE listener queues.
    Enables low-latency real-time broadcasting to all active frontend dashboards.
    """

    def __init__(self):
        self.active_websockets: Set[WebSocket] = set()
        self.sse_queues: Set[asyncio.Queue] = set()

    async def connect_ws(self, websocket: WebSocket):
        await websocket.accept()
        self.active_websockets.add(websocket)
        logger.info(f"WebSocket client connected. Active connections: {len(self.active_websockets)}")

    def disconnect_ws(self, websocket: WebSocket):
        self.active_websockets.discard(websocket)
        logger.info(f"WebSocket client disconnected. Active connections: {len(self.active_websockets)}")

    def register_sse_client(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self.sse_queues.add(queue)
        logger.info(f"SSE client registered. Active SSE clients: {len(self.sse_queues)}")
        return queue

    def unregister_sse_client(self, queue: asyncio.Queue):
        self.sse_queues.discard(queue)
        logger.info(f"SSE client unregistered. Active SSE clients: {len(self.sse_queues)}")

    async def broadcast(self, event_type: str, data: Dict[str, Any]):
        """
        Broadcasts an event message concurrently to all connected WebSocket
        and SSE subscribers.
        """
        payload = {
            "type": event_type,
            "data": data,
        }
        message_json = json.dumps(payload, default=str)

        # 1. Broadcast to WebSockets
        ws_tasks = []
        dead_websockets = []
        for ws in self.active_websockets:
            try:
                ws_tasks.append(ws.send_text(message_json))
            except Exception:
                dead_websockets.append(ws)

        for dead_ws in dead_websockets:
            self.active_websockets.discard(dead_ws)

        if ws_tasks:
            results = await asyncio.gather(*ws_tasks, return_exceptions=True)
            for ws, res in zip(list(self.active_websockets), results):
                if isinstance(res, Exception):
                    logger.warning(f"Error sending to websocket client: {res}")
                    self.active_websockets.discard(ws)

        # 2. Dispatch to SSE queues
        dead_queues = []
        for queue in self.sse_queues:
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                logger.warning("SSE queue full, dropping message for slow consumer.")
            except Exception:
                dead_queues.append(queue)

        for dq in dead_queues:
            self.sse_queues.discard(dq)


ws_manager = ConnectionManager()
