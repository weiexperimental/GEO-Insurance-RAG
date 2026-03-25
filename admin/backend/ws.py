from fastapi import WebSocket
from datetime import datetime, timezone


class ConnectionManager:
    def __init__(self):
        self.active: list[WebSocket] = []
        self._snapshot: dict = {}

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)

    async def broadcast(self, message: dict):
        dead = []
        for ws in self.active:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

    async def send_snapshot(self, ws: WebSocket):
        if self._snapshot:
            await ws.send_json({
                "type": "snapshot",
                "data": self._snapshot,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

    def update_snapshot(self, data: dict):
        self._snapshot.update(data)
