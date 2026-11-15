import asyncio
import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import StreamingResponse

from app.core.ws_manager import ws_manager

logger = logging.getLogger("pulseops.realtime")

router = APIRouter(tags=["Real-time Streaming"])


@router.websocket("/ws/live")
async def websocket_live_stream(websocket: WebSocket):
    """
    Real-time bidirectional WebSocket channel.
    Streams live deployment updates, health check probes, and incident alerts.
    """
    await ws_manager.connect_ws(websocket)
    try:
        # Keep-alive loop with ping/pong
        while True:
            # Wait for client heartbeat or messages
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
            except Exception:
                pass
    except WebSocketDisconnect:
        ws_manager.disconnect_ws(websocket)
    except Exception as e:
        logger.warning(f"WebSocket client disconnected with exception: {e}")
        ws_manager.disconnect_ws(websocket)


@router.get("/sse/events")
async def sse_event_stream(request: Request):
    """
    Server-Sent Events (SSE) alternative for firewalled/corporate proxy environments
    that block WebSockets.
    """
    queue = ws_manager.register_sse_client()

    async def event_generator():
        try:
            # Yield initial connection confirmation
            yield f"event: connected\ndata: {json.dumps({'status': 'connected'})}\n\n"

            while True:
                # Disconnect if client aborted connection
                if await request.is_disconnected():
                    break

                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=15.0)
                    event_type = payload.get("type", "message")
                    data_str = json.dumps(payload.get("data", {}), default=str)
                    yield f"event: {event_type}\ndata: {data_str}\n\n"
                except asyncio.TimeoutError:
                    # Send periodic keep-alive comment every 15s to prevent Render 504 proxy timeout
                    yield ": keepalive\n\n"
        finally:
            ws_manager.unregister_sse_client(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
