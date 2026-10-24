import asyncio
import json
import logging
from typing import List, Dict, Any
from fastapi import WebSocket

logger = logging.getLogger(__name__)


class AlertConnectionManager:
    """Thread-safe WebSocket manager broadcasting AI incident events to dashboard clients."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stream_status: Dict[str, bool] = {}

    def set_event_loop(self, loop: asyncio.AbstractEventLoop):
        self._loop = loop

    def set_stream_status(self, camera_id: str, is_active: bool):
        """Registers the health/activity status of a camera stream."""
        self._stream_status[camera_id] = bool(is_active)

    def is_stream_active(self, camera_id: str) -> bool:
        """
        Returns True if the camera stream is currently active with valid live frames.
        Returns False if the stream is offline, unassigned, or rendering STREAM OFFLINE.
        """
        return self._stream_status.get(camera_id, True)

    def pause_stream_dispatch(self, camera_id: str):
        """Circuit breaker: completely pauses/stops alert dispatch for the specified camera."""
        self._stream_status[camera_id] = False

    def resume_stream_dispatch(self, camera_id: str):
        """Circuit breaker: resumes alert dispatch once valid live frames pass inference."""
        self._stream_status[camera_id] = True

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"Alert WebSocket client connected. Active connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"Alert WebSocket client disconnected. Remaining: {len(self.active_connections)}")

    async def broadcast(self, message: Dict[str, Any]):
        if not self.active_connections:
            return

        # Circuit Breaker: Kill event dispatch for offline, unassigned, or invalid camera streams
        cam = message.get("camera")
        if cam and not self.is_stream_active(cam):
            logger.warning(
                f"Circuit Breaker: Alert {message.get('id')} suppressed because {cam} is OFFLINE / INACTIVE."
            )
            return

        payload = json.dumps(message)
        dead_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_text(payload)
            except Exception as e:
                logger.warning(f"Error transmitting to alert WebSocket client: {e}")
                dead_connections.append(connection)
        for dead in dead_connections:
            self.disconnect(dead)

    def broadcast_sync(self, message: Dict[str, Any]):
        """Thread-safe synchronous broadcast dispatchable from background worker threads."""
        if not self.active_connections:
            return

        # Circuit Breaker: Kill event dispatch for offline, unassigned, or invalid camera streams
        cam = message.get("camera")
        if cam and not self.is_stream_active(cam):
            logger.warning(
                f"Circuit Breaker: Alert {message.get('id')} suppressed because {cam} is OFFLINE / INACTIVE."
            )
            return

        try:
            loop = self._loop
            if loop and loop.is_running():
                asyncio.run_coroutine_threadsafe(self.broadcast(message), loop)
            else:
                try:
                    cur_loop = asyncio.get_running_loop()
                    cur_loop.create_task(self.broadcast(message))
                except RuntimeError:
                    asyncio.run(self.broadcast(message))
        except Exception as e:
            logger.error(f"Error in AlertConnectionManager.broadcast_sync: {e}")


alert_manager = AlertConnectionManager()
