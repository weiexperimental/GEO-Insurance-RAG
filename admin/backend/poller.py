import asyncio
import os
import json
from datetime import datetime, timezone
from admin.backend.services.opensearch import OpenSearchService
from admin.backend.ws import ConnectionManager


class Poller:
    def __init__(
        self,
        os_service: OpenSearchService,
        ws_manager: ConnectionManager,
        log_dir: str = "./logs",
    ):
        self._os = os_service
        self._ws = ws_manager
        self._log_dir = log_dir
        self._last_snapshot: dict = {}
        self._last_log_pos: int = 0
        self._last_log_file: str = ""
        self._running = False

    def _compute_diff(self, old: dict, new: dict) -> dict:
        return {k: v for k, v in new.items() if old.get(k) != v}

    async def _poll_system_health(self) -> dict:
        try:
            health = self._os.get_cluster_health()
            nodes = self._os.get_node_stats()
            indices = self._os.get_index_stats()
            overview = self._os.get_system_overview()
            knn = self._os.get_knn_stats()
            return {
                "system_health": {
                    "cluster": health,
                    "nodes": nodes,
                    "indices": indices,
                    "overview": overview,
                    "knn": knn,
                }
            }
        except Exception:
            return {"system_health": {"cluster": {"status": "disconnected"}}}

    async def _poll_ingestion(self) -> dict:
        try:
            active = self._os.get_active_ingestions()
        except Exception:
            active = []
        return {"ingestion": {"active": active, "pipeline": {"busy": len(active) > 0}}}

    async def _poll_logs(self) -> list[dict]:
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = os.path.join(self._log_dir, f"rag-{today}.log")

        if log_file != self._last_log_file:
            self._last_log_file = log_file
            self._last_log_pos = 0

        if not os.path.exists(log_file):
            return []

        try:
            size = os.path.getsize(log_file)
            if size <= self._last_log_pos:
                return []

            entries = []
            with open(log_file, "r") as f:
                f.seek(self._last_log_pos)
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entries.append(json.loads(line))
                        except json.JSONDecodeError:
                            entries.append({"raw": line})
                self._last_log_pos = f.tell()
            return entries
        except Exception:
            return []

    async def poll_once(self):
        data = {}
        health = await self._poll_system_health()
        data.update(health)
        ingestion = await self._poll_ingestion()
        data.update(ingestion)

        diff = self._compute_diff(self._last_snapshot, data)
        if diff:
            self._last_snapshot.update(data)
            self._ws.update_snapshot(self._last_snapshot)
            now = datetime.now(timezone.utc).isoformat()
            for key, value in diff.items():
                msg_type = "system_health" if key == "system_health" else "ingestion_update"
                await self._ws.broadcast({"type": msg_type, "data": value, "timestamp": now})

        log_entries = await self._poll_logs()
        if log_entries:
            now = datetime.now(timezone.utc).isoformat()
            for entry in log_entries:
                await self._ws.broadcast({"type": "log_entry", "data": entry, "timestamp": now})

    async def run(self):
        self._running = True
        tick = 0
        while self._running:
            await asyncio.sleep(1)
            tick += 1

            if tick % 2 == 0:
                log_entries = await self._poll_logs()
                if log_entries:
                    now = datetime.now(timezone.utc).isoformat()
                    for entry in log_entries:
                        await self._ws.broadcast({"type": "log_entry", "data": entry, "timestamp": now})

            if tick % 5 == 0:
                ingestion = await self._poll_ingestion()
                if ingestion:
                    diff = self._compute_diff(
                        {"ingestion": self._last_snapshot.get("ingestion")},
                        {"ingestion": ingestion.get("ingestion")},
                    )
                    if diff:
                        self._last_snapshot.update(ingestion)
                        self._ws.update_snapshot(self._last_snapshot)
                        now = datetime.now(timezone.utc).isoformat()
                        await self._ws.broadcast({"type": "ingestion_update", "data": ingestion["ingestion"], "timestamp": now})

            if tick % 15 == 0:
                health = await self._poll_system_health()
                if health:
                    diff = self._compute_diff(
                        {"system_health": self._last_snapshot.get("system_health")},
                        health,
                    )
                    if diff:
                        self._last_snapshot.update(health)
                        self._ws.update_snapshot(self._last_snapshot)
                        now = datetime.now(timezone.utc).isoformat()
                        await self._ws.broadcast({"type": "system_health", "data": health["system_health"], "timestamp": now})

    def stop(self):
        self._running = False
