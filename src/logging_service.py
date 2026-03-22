# src/logging_service.py
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class RAGLogger:
    def __init__(self, log_dir: str, opensearch_client: Any | None = None):
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._os_client = opensearch_client
        self._log_file = self._log_dir / f"rag-{datetime.now().strftime('%Y-%m-%d')}.log"

    def log(
        self,
        document: str,
        stage: str,
        status: str,
        duration_ms: int = 0,
        details: dict | None = None,
    ) -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "document": document,
            "stage": stage,
            "status": status,
            "duration_ms": duration_ms,
            "details": details or {},
        }

        # Always write to file
        with open(self._log_file, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        # Try writing to OpenSearch
        if self._os_client:
            try:
                self._os_client.index(index="rag-logs", body=entry)
            except Exception:
                pass  # File log is the fallback
