"""Named seam for the eventual WebSocket node connection (M1's aiohttp server).

Deliberately empty at M0: there is no socket, no server, and no node yet — see `docs/m0-plan.md`
§6.4. The name is reserved now, matching `hdp_bridge/connection.py`'s eventual M2 filename, so
M1 writes into a file that already exists rather than inventing the name under time pressure and
so the M2 extraction (ADR-0004) is `git mv` plus import fixes.
"""
