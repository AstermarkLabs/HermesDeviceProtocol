"""Fault injection for the conformance suite (m1-plan.md §7).

Every fault is driven through the node's CLI (`--fault FLAG`, repeatable) — never by a test
importing `hdp_reference_node` internals and monkeypatching them. That's the M1-4 review rule
this shape exists to make easy to follow: the conformance suite is written against the protocol
and the wire, not against this package, so M5's Android node can reuse the same harness unchanged
(m1-plan.md §9, §7).
"""

from __future__ import annotations

from dataclasses import dataclass

_FLAG_NAMES = frozenset(
    {
        "never-ack",
        "slow-result",
        "malformed-result",
        "drop-connection-mid-call",
        "ignore-cancel",
        "stale-schema",
        "duplicate-result",
    }
)


@dataclass(frozen=True)
class FaultConfig:
    never_ack: bool = False
    slow_result_ms: int | None = None
    malformed_result: bool = False
    drop_connection_mid_call: bool = False
    ignore_cancel: bool = False
    stale_schema: bool = False
    duplicate_result: bool = False

    @classmethod
    def parse(cls, flags: list[str]) -> FaultConfig:
        """Parse a list of `--fault` flag values, e.g. `["never-ack", "slow-result=4000"]`."""
        kwargs: dict[str, object] = {}
        for flag in flags:
            name, _, value = flag.partition("=")
            name = name.strip()
            if name not in _FLAG_NAMES:
                raise ValueError(f"unknown fault flag: {name!r}")
            if name == "slow-result":
                if not value:
                    raise ValueError(
                        "slow-result requires a millisecond value, e.g. slow-result=4000"
                    )
                kwargs["slow_result_ms"] = int(value)
            else:
                kwargs[name.replace("-", "_")] = True
        return cls(**kwargs)
