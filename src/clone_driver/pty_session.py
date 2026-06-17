from __future__ import annotations

import os
import pty
import selectors
import subprocess
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class PtyReadResult:
    transcript: str
    matched: bool


class PtyWorker:
    def __init__(self, command: list[str]):
        if not command:
            raise ValueError("worker command is required")
        master_fd, slave_fd = pty.openpty()
        self.master_fd = master_fd
        self.process = subprocess.Popen(
            command,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            close_fds=True,
        )
        os.close(slave_fd)
        self._selector = selectors.DefaultSelector()
        self._selector.register(master_fd, selectors.EVENT_READ)
        self.transcript = ""

    def read_until(self, marker: str, timeout_seconds: float) -> str:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if marker and marker in self.transcript:
                return self.transcript
            remaining = max(0.0, deadline - time.monotonic())
            events = self._selector.select(timeout=min(0.05, remaining))
            for key, _ in events:
                try:
                    chunk = os.read(key.fd, 4096)
                except OSError:
                    return self.transcript
                if not chunk:
                    return self.transcript
                self.transcript += chunk.decode("utf-8", errors="replace")
        return self.transcript

    def send_line(self, text: str) -> None:
        os.write(self.master_fd, (text + "\n").encode("utf-8"))

    def is_running(self) -> bool:
        return self.process.poll() is None

    def close(self) -> None:
        try:
            self._selector.unregister(self.master_fd)
        except Exception:
            pass
        try:
            os.close(self.master_fd)
        except OSError:
            pass
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=1)
