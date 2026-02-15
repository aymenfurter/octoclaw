"""Cloudflare quick-tunnel manager."""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import threading
from time import sleep
from time import time as _time
from typing import Any

from ..util.result import Result

logger = logging.getLogger(__name__)


class CloudflareTunnel:
    """Manages a ``cloudflared tunnel --url`` subprocess."""

    def __init__(self) -> None:
        self._proc: subprocess.Popen | None = None
        self.url: str | None = None

    @property
    def is_active(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def stop(self) -> Result:
        """Terminate the tunnel subprocess."""
        if not self.is_active:
            return Result.ok("Tunnel is not running")
        try:
            assert self._proc is not None
            self._proc.terminate()
            self._proc.wait(timeout=5)
        except Exception:
            if self._proc is not None:
                self._proc.kill()
        self._proc = None
        self.url = None
        return Result.ok("Tunnel stopped")

    def start(self, port: int) -> Result:
        if self.is_active:
            return Result.ok("Tunnel already running", value=self.url)
        if not shutil.which("cloudflared"):
            return Result.fail("cloudflared not found.")
        try:
            proc = subprocess.Popen(
                ["cloudflared", "tunnel", "--url", f"http://127.0.0.1:{port}"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            url = self._wait_for_url(proc)
            if url:
                self._proc = proc
                self.url = url
                self._drain_background(proc)
                return Result.ok("Tunnel started successfully", value=url)
            proc.terminate()
            return Result.fail("Could not detect tunnel URL within 20 s")
        except Exception as exc:
            return Result.fail(f"Failed to start tunnel: {exc}")

    @staticmethod
    def _wait_for_url(proc: subprocess.Popen, timeout: float = 20) -> str | None:
        start = _time()
        while _time() - start < timeout:
            line = proc.stderr.readline().decode("utf-8", errors="replace")
            if not line:
                sleep(0.2)
                continue
            match = re.search(r"(https://[\w-]+\.trycloudflare\.com)", line)
            if match:
                return match.group(1)
        return None

    @staticmethod
    def _drain_background(proc: subprocess.Popen) -> None:
        for stream in (proc.stdout, proc.stderr):
            threading.Thread(target=_drain, args=(stream,), daemon=True).start()


def _drain(stream: Any) -> None:
    try:
        for _ in stream:
            pass
    except Exception:
        pass
