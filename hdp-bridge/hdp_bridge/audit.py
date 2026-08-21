"""Append-only JSONL audit writer (§3.5, §6.3). `O_APPEND|O_CREAT`, 0600, one JSON object per
line, `fsync` on the security-relevant subset, daily rotation by filename."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

_FSYNC_EVENTS = frozenset(
    {
        "paired",
        "pairing_code_minted",
        "revoked",
        "auth_failed",
        "daemon_start",
        "daemon_stop",
        "rejected_control_verb",
        "approval_decided",
        "policy_changed",
    }
)


class AuditWriter:
    def __init__(self, audit_dir: Path) -> None:
        self._audit_dir = audit_dir
        self._audit_dir.mkdir(parents=True, exist_ok=True)

    def _current_path(self) -> Path:
        day = time.strftime("%Y-%m-%d", time.gmtime())
        return self._audit_dir / f"audit-{day}.jsonl"

    def record(self, event: str, **fields) -> None:
        path = self._current_path()
        line = json.dumps({"event": event, "ts": int(time.time() * 1000), **fields}) + "\n"
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(fd, line.encode("utf-8"))
            if event in _FSYNC_EVENTS:
                os.fsync(fd)
        finally:
            os.close(fd)

    def read_today(self) -> list[dict]:
        """Today's audit records, parsed. Backs `control.py`'s `ctl_audit_tail` verb — reads
        through *this* writer's own `_audit_dir`, not a path re-derived from `config` at the call
        site, so the control server always reports whatever directory it actually opened (matters
        for tests that wire a `tmp_path`-scoped `AuditWriter` directly, and for profile
        isolation in general)."""
        path = self._current_path()
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
