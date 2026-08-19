"""Fail-closed HDP permission policy evaluation and reloads."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from threading import Lock
from typing import Literal


class Mode(StrEnum):
    """The complete set of policy outcomes. There is intentionally no bare allow mode."""

    DENY = "deny"
    ASK = "ask"
    SESSION = "session"
    DEVICE = "device"
    ALWAYS = "always"


DecisionSource = Literal["device_capability", "device_default", "global_default", "fallback"]
_CAPABILITY_RE = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")
_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class Decision:
    """A policy result with enough provenance for audit records."""

    mode: Mode
    source: DecisionSource
    policy_seq: int


class PolicyValidationError(ValueError):
    """Raised when a policy document cannot be used safely."""


@dataclass(frozen=True)
class PolicyTable:
    """An immutable, validated policy snapshot."""

    defaults: tuple[tuple[str, Mode], ...]
    devices: tuple[tuple[str, tuple[tuple[str, Mode], ...]], ...]
    policy_seq: int

    @classmethod
    def from_data(cls, data: object, *, policy_seq: int) -> PolicyTable:
        """Validate decoded policy data and construct one immutable snapshot."""
        if not isinstance(data, dict):
            raise PolicyValidationError("policy document must be a mapping")
        if data.get("version") != 1:
            raise PolicyValidationError("policy version must be exactly 1")

        if set(data) - {"version", "defaults", "devices", "default_device"}:
            raise PolicyValidationError("policy contains unsupported top-level keys")
        defaults = cls._parse_modes(data.get("defaults", {}), "defaults", permit_default=False)
        raw_devices = data.get("devices", {})
        if not isinstance(raw_devices, dict):
            raise PolicyValidationError("devices must be a mapping")
        devices: list[tuple[str, tuple[tuple[str, Mode], ...]]] = []
        for device_id, raw_modes in raw_devices.items():
            if not isinstance(device_id, str):
                raise PolicyValidationError("device identifiers must be strings")
            devices.append(
                (
                    device_id,
                    cls._parse_modes(raw_modes, f"devices.{device_id}", permit_default=True),
                )
            )
        return cls(tuple(defaults), tuple(devices), policy_seq)

    @staticmethod
    def _parse_modes(
        value: object, location: str, *, permit_default: bool
    ) -> tuple[tuple[str, Mode], ...]:
        if not isinstance(value, dict):
            raise PolicyValidationError(f"{location} must be a mapping")
        modes: list[tuple[str, Mode]] = []
        for capability, raw_mode in value.items():
            if not isinstance(capability, str):
                raise PolicyValidationError(f"{location} contains a non-string capability")
            if capability != "default" and _CAPABILITY_RE.fullmatch(capability) is None:
                raise PolicyValidationError(
                    f"{location}.{capability} is not a valid capability name"
                )
            if capability == "default" and not permit_default:
                raise PolicyValidationError("defaults cannot contain a device default")
            if not isinstance(raw_mode, str):
                raise PolicyValidationError(f"{location}.{capability} mode must be a string")
            try:
                mode = Mode(raw_mode)
            except ValueError as exc:
                raise PolicyValidationError(
                    f"{location}.{capability} has unsupported mode {raw_mode!r}"
                ) from exc
            modes.append((capability, mode))
        return tuple(modes)

    def resolve(self, device_id: str, capability: str) -> Decision:
        """Resolve a device/capability pair using the documented four layers."""
        device_modes = self._device_modes(device_id)
        if device_modes is not None:
            for configured_capability, mode in device_modes:
                if configured_capability == capability:
                    return Decision(mode, "device_capability", self.policy_seq)
            for configured_capability, mode in device_modes:
                if configured_capability == "default":
                    return Decision(mode, "device_default", self.policy_seq)
        for configured_capability, mode in self.defaults:
            if configured_capability == capability:
                return Decision(mode, "global_default", self.policy_seq)
        return Decision(Mode.DENY, "fallback", self.policy_seq)

    def _device_modes(self, device_id: str) -> tuple[tuple[str, Mode], ...] | None:
        for configured_device, modes in self.devices:
            if configured_device == device_id:
                return modes
        return None


class _NoDuplicateSafeLoader:  # pragma: no cover - completed dynamically when PyYAML is available
    """Marker used to keep the PyYAML import out of module import paths."""


class PolicyEngine:
    """Own the current immutable policy snapshot and safely replace it after validation."""

    def __init__(self, path: Path, *, known_device_ids: set[str] | None = None) -> None:
        self._path = path
        self._known_device_ids = known_device_ids
        self._lock = Lock()
        self._table = PolicyTable((), (), policy_seq=0)
        self._file_token: tuple[int, int, int] | None = None

    @property
    def table(self) -> PolicyTable:
        """Capture the current immutable policy snapshot."""
        return self._table

    def resolve(self, device_id: str, capability: str) -> Decision:
        """Resolve against one captured table reference."""
        return self._table.resolve(device_id, capability)

    def reload(self, *, force: bool = False) -> bool:
        """Parse and validate the on-disk document before atomically replacing the current table."""
        try:
            stat = self._path.stat()
            token = (stat.st_mtime_ns, stat.st_size, stat.st_ino)
            if not force and token == self._file_token:
                return False
            data = self._load_yaml(self._path.read_bytes())
            if self._known_device_ids is not None:
                self._validate_known_devices(data)
            table = PolicyTable.from_data(data, policy_seq=self._table.policy_seq + 1)
        except (OSError, PolicyValidationError, RuntimeError, ValueError) as exc:
            _LOGGER.error(
                "retaining policy sequence %s after rejected reload of %s: %s",
                self._table.policy_seq,
                self._path,
                exc,
            )
            return False
        with self._lock:
            self._table = table
            self._file_token = token
        return True

    @staticmethod
    def _load_yaml(contents: bytes) -> object:
        try:
            import yaml
        except ImportError as exc:  # pragma: no cover - dependency metadata supplies PyYAML
            raise RuntimeError("PyYAML is required to load policy.yaml") from exc

        class NoDuplicateLoader(yaml.SafeLoader):
            pass

        def construct_mapping(
            loader: yaml.SafeLoader, node: yaml.MappingNode, deep: bool = False
        ) -> dict[object, object]:
            mapping: dict[object, object] = {}
            for key_node, value_node in node.value:
                key = loader.construct_object(key_node, deep=deep)
                if key in mapping:
                    raise PolicyValidationError(f"duplicate policy key {key!r}")
                mapping[key] = loader.construct_object(value_node, deep=deep)
            return mapping

        NoDuplicateLoader.add_constructor(
            yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, construct_mapping
        )
        try:
            loaded = yaml.load(contents, Loader=NoDuplicateLoader)  # noqa: S506 - SafeLoader subclass
        except yaml.YAMLError as exc:
            raise PolicyValidationError(f"invalid YAML: {exc}") from exc
        return {} if loaded is None else loaded

    def _validate_known_devices(self, data: object) -> None:
        if not isinstance(data, dict):
            return
        devices = data.get("devices", {})
        if not isinstance(devices, dict):
            return
        unknown = set(devices) - self._known_device_ids
        if unknown:
            raise PolicyValidationError(
                f"policy names unknown device(s): {', '.join(sorted(unknown))}"
            )
