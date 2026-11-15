"""Runs inside the API server: every minute, collect finished batches and send more (tagging.batches.tick).
Batches take minutes to hours, so the laptop can sleep in between; the next tick catches up."""

import logging
import threading

from photoindex.db import session_scope
from photoindex.sources import get_source

log = logging.getLogger(__name__)
INTERVAL = 60


class _TagWorker:
    def __init__(self):
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None
        self.last: dict | None = None
        self.last_error: str | None = None

    def start(self) -> None:
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._run, name="tag-worker", daemon=True)
            self._thread.start()

    def wake(self) -> None:
        self._wake.set()

    def _run(self) -> None:
        from photoindex.tagging.batches import tick

        source = None
        while True:
            try:
                source = source or get_source()
                with session_scope() as session:
                    self.last = tick(session, source)
                self.last_error = None
            except Exception as e:  # keep going; a network blip or a full cap shouldn't stop the worker
                log.exception("tag worker tick failed")
                self.last_error = str(e)[:300]
            self._wake.wait(INTERVAL)
            self._wake.clear()


worker = _TagWorker()
