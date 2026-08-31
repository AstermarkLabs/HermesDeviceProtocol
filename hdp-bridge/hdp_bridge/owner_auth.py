"""Fresh local owner authorization through the host OS's Polkit/PAM stack."""

from __future__ import annotations

import asyncio
import shutil


class PolkitOwnerAuthorizer:
    """Use `pkexec` so HDP never reads or handles an owner password itself."""

    async def authorize_pairing(self) -> bool:
        pkexec = shutil.which("pkexec")
        if pkexec is None:
            return False
        try:
            process = await asyncio.create_subprocess_exec(pkexec, "/usr/bin/true")
            return await process.wait() == 0
        except OSError:
            return False
