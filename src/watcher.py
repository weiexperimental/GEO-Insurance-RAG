# src/watcher.py
import os
import threading
import time
from pathlib import Path
from typing import Callable

from watchdog.events import FileSystemEventHandler, FileCreatedEvent
from watchdog.observers import Observer


class _PDFHandler(FileSystemEventHandler):
    def __init__(self, on_new_file: Callable[[str], None], stabilization_seconds: float = 3.0):
        self._on_new_file = on_new_file
        self._stabilization = stabilization_seconds
        self._pending: dict[str, float] = {}
        self._lock = threading.Lock()
        self._running = True
        self._checker = threading.Thread(target=self._check_loop, daemon=True)
        self._checker.start()

    def stop(self):
        self._running = False

    def on_created(self, event: FileCreatedEvent) -> None:
        if event.is_directory:
            return
        if not event.src_path.lower().endswith(".pdf"):
            return
        with self._lock:
            self._pending[event.src_path] = time.time()

    def _check_loop(self) -> None:
        while self._running:
            time.sleep(0.1)
            ready = []
            with self._lock:
                now = time.time()
                for path, first_seen in list(self._pending.items()):
                    if not os.path.exists(path):
                        del self._pending[path]
                        continue
                    if now - first_seen >= self._stabilization:
                        ready.append(path)
                        del self._pending[path]

            for path in ready:
                self._on_new_file(path)


class InboxWatcher:
    def __init__(self, inbox_dir: str, on_new_file: Callable[[str], None], stabilization_seconds: float = 3.0):
        self._inbox_dir = inbox_dir
        self._handler = _PDFHandler(on_new_file, stabilization_seconds)
        self._observer = Observer()
        self._observer.schedule(self._handler, inbox_dir, recursive=False)

    def start(self) -> None:
        self._observer.start()

    def stop(self) -> None:
        self._handler.stop()
        self._observer.stop()
        self._observer.join(timeout=5)
