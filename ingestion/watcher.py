from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Callable

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

log = logging.getLogger("evg.watcher")

IngestCallback = Callable[[Path], None]


class _Handler(FileSystemEventHandler):
    def __init__(self, on_file: IngestCallback) -> None:
        self.on_file = on_file

    def on_created(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        try:
            self.on_file(Path(event.src_path))
        except Exception as e:  # noqa: BLE001
            log.warning("watcher ingest callback failed: %s", e)

    def on_moved(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        dest = getattr(event, "dest_path", None)
        if not dest:
            return
        try:
            self.on_file(Path(dest))
        except Exception as e:  # noqa: BLE001
            log.warning("watcher move callback failed: %s", e)


class FolderWatcher:
    def __init__(self, roots: list[Path], on_file: IngestCallback) -> None:
        self.roots = [r for r in roots if r.exists() and r.is_dir()]
        self.on_file = on_file
        self._observer: Observer | None = None
        self._lock = threading.Lock()

    def start(self) -> None:
        with self._lock:
            if self._observer:
                return
            obs = Observer()
            handler = _Handler(self.on_file)
            for root in self.roots:
                obs.schedule(handler, str(root), recursive=True)
                log.info("watching %s", root)
            obs.daemon = True
            obs.start()
            self._observer = obs

    def stop(self) -> None:
        with self._lock:
            if self._observer:
                self._observer.stop()
                self._observer.join(timeout=5)
                self._observer = None
