"""Host adapter for the Android USB-accessory bootstrap line protocol."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import BinaryIO

from .usb_bootstrap import UsbBootstrapApproval, UsbBootstrapPeer, UsbBootstrapRequest

_MAX_FRAME_BYTES = 16 * 1024
logger = logging.getLogger(__name__)


class UsbAccessoryPeer(UsbBootstrapPeer):
    """A physically opened USB accessory; never a TCP or Bluetooth transport."""

    def __init__(self, stream: BinaryIO, *, device_pubkey: str, candidate_name: str) -> None:
        self._stream = stream
        self.device_pubkey = device_pubkey
        self.candidate_name = candidate_name

    @classmethod
    def open(cls, path: Path) -> UsbAccessoryPeer:
        stream = path.open("r+b", buffering=0)
        try:
            frame = _read_frame(stream)
            payload = _payload(frame, "usb_candidate_hello")
            return cls(
                stream,
                device_pubkey=_required_string(payload, "device_pubkey"),
                candidate_name=_required_string(payload, "candidate_name"),
            )
        except BaseException:
            stream.close()
            raise

    @classmethod
    def open_android_accessory(cls, serial: str | None = None) -> UsbAccessoryPeer:
        """Switch one Android device into Accessory mode and claim its bulk interface."""
        import usb.core
        import usb.util

        try:
            device, protocol = _find_android(usb.core, serial)
        except Exception as exc:  # noqa: BLE001
            raise UsbAccessoryError("probing Android Accessory support", exc) from exc
        for index, value in enumerate(
            ("Hermes", "HDP", "USB pairing", "1", "https://hermes.local", "")
        ):
            device.ctrl_transfer(0x40, 52, 0, index, value.encode())
        try:
            device.ctrl_transfer(0x40, 53, 0, 0, None)
        except Exception as exc:  # noqa: BLE001
            raise UsbAccessoryError("requesting Android Accessory mode", exc) from exc
        # Android disconnects and re-enumerates after ACCESSORY_START. Retaining this handle
        # can leave libusb's old claim alive long enough for the new interface to report EBUSY.
        usb.util.dispose_resources(device)
        try:
            accessory = _wait_for_accessory(usb.core, serial)
        except Exception as exc:  # noqa: BLE001
            raise UsbAccessoryError("waiting for Android Accessory re-enumeration", exc) from exc
        try:
            configuration = accessory.get_active_configuration()
        except usb.core.USBError:
            accessory.set_configuration()
            configuration = accessory.get_active_configuration()
        interface = configuration[(0, 0)]
        if accessory.is_kernel_driver_active(interface.bInterfaceNumber):
            accessory.detach_kernel_driver(interface.bInterfaceNumber)
        try:
            usb.util.claim_interface(accessory, interface.bInterfaceNumber)
        except Exception as exc:  # noqa: BLE001
            raise UsbAccessoryError("claiming Android Accessory bulk interface", exc) from exc
        stream = _LibusbStream(accessory, interface, usb.util)
        try:
            frame = _read_frame(stream)
            payload = _payload(frame, "usb_candidate_hello")
            return cls(
                stream,
                device_pubkey=_required_string(payload, "device_pubkey"),
                candidate_name=_required_string(payload, "candidate_name"),
            )
        except BaseException:
            stream.close()
            raise

    def close(self) -> None:
        self._stream.close()

    async def deliver_enrollment(self, request: UsbBootstrapRequest) -> UsbBootstrapApproval | None:
        try:
            return await asyncio.to_thread(self._deliver, request)
        except (OSError, ValueError, UnicodeDecodeError):
            return None

    def _deliver(self, request: UsbBootstrapRequest) -> UsbBootstrapApproval:
        _write_frame(
            self._stream,
            "usb_bootstrap_request",
            {
                "enrollment_id": request.enrollment_id,
                "host_public_key": request.host_public_key,
                "host_signature": request.host_signature,
                "expires_at_ms": request.expires_at_ms,
                "endpoint": request.endpoint,
                "tls_pin": request.tls_pin,
            },
        )
        payload = _payload(_read_frame(self._stream), "usb_bootstrap_approval")
        return UsbBootstrapApproval(
            enrollment_id=_required_string(payload, "enrollment_id"),
            host_fingerprint=_required_string(payload, "host_fingerprint"),
            device_public_key=_required_string(payload, "device_public_key"),
            candidate_signature=_required_string(payload, "candidate_signature"),
        )


class UsbAccessoryError(RuntimeError):
    def __init__(self, stage: str, cause: Exception) -> None:
        super().__init__(f"{stage} failed: {cause}")


def _read_frame(stream: BinaryIO) -> dict:
    data = stream.readline(_MAX_FRAME_BYTES + 1)
    if not data or len(data) > _MAX_FRAME_BYTES or not data.endswith(b"\n"):
        raise ValueError("invalid USB bootstrap frame")
    value = json.loads(data[:-1].decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("USB bootstrap frame must be an object")
    return value


def _write_frame(stream: BinaryIO, frame_type: str, payload: dict[str, object]) -> None:
    encoded = json.dumps({"type": frame_type, "payload": payload}, separators=(",", ":")).encode()
    if len(encoded) > _MAX_FRAME_BYTES:
        raise ValueError("USB bootstrap frame is too large")
    stream.write(encoded + b"\n")
    stream.flush()


def _payload(frame: dict, expected_type: str) -> dict:
    if frame.get("type") != expected_type or not isinstance(frame.get("payload"), dict):
        raise ValueError("unexpected USB bootstrap frame")
    return frame["payload"]


def _required_string(payload: dict, name: str) -> str:
    value = payload.get(name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"missing USB field {name}")
    return value


def _find_android(core: object, serial: str | None):
    """Probe devices instead of guessing Android from VID (Pixels use Google's VID too)."""
    matches = []
    for item in core.find(find_all=True):
        try:
            if serial is not None and item.serial_number != serial:
                continue
            protocol = item.ctrl_transfer(0xC0, 51, 0, 0, 2, timeout=1_000)
            if len(protocol) == 2:
                matches.append((item, protocol))
        except Exception as exc:  # noqa: BLE001 -- non-Android USB devices reject the AOA probe
            logger.debug("USB device rejected Android Accessory probe: %s", exc)
    if len(matches) != 1:
        hint = "matching" if serial is not None else "Accessory-capable"
        raise ValueError(f"expected exactly one {hint} Android USB device, found {len(matches)}")
    return matches[0]


def _wait_for_accessory(core: object, serial: str | None):
    import time

    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        for item in core.find(find_all=True, idVendor=0x18D1):
            if item.idProduct in {0x2D00, 0x2D01} and (
                serial is None or getattr(item, "serial_number", None) == serial
            ):
                return item
        time.sleep(0.1)
    raise TimeoutError("Android device did not re-enumerate in Accessory mode")


class _LibusbStream:
    def __init__(self, device: object, interface: object, util: object) -> None:
        self._device, self._util = device, util
        endpoints = list(interface)
        self._in = next(
            endpoint.bEndpointAddress for endpoint in endpoints if endpoint.bEndpointAddress & 0x80
        )
        self._out = next(
            endpoint.bEndpointAddress
            for endpoint in endpoints
            if not endpoint.bEndpointAddress & 0x80
        )
        self._buffer = bytearray()

    def readline(self, limit: int) -> bytes:
        while b"\n" not in self._buffer:
            self._buffer.extend(self._device.read(self._in, min(limit, 4096), timeout=10_000))
            if len(self._buffer) > limit:
                return bytes(self._buffer)
        end = self._buffer.index(b"\n") + 1
        result, self._buffer = bytes(self._buffer[:end]), self._buffer[end:]
        return result

    def write(self, data: bytes) -> int:
        return int(self._device.write(self._out, data, timeout=10_000))

    def flush(self) -> None:
        return None

    def close(self) -> None:
        self._util.dispose_resources(self._device)
