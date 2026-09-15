"""Cloud client for the Gree Plus integration."""

from dataclasses import dataclass, field
import hashlib
import json
import time
from typing import Any
import uuid

from aiohttp import ClientError, ClientSession, ClientTimeout

from .GRConst import OP_CLIENT_ID, OP_CLIENT_SECRET
from .GROauthControl import OpenPlatformHost, get_openplatform_host

_SMARTHOME_PATH = "/standard/v1/smarthome"
_REQUEST_TIMEOUT = ClientTimeout(total=10.0)


class GreeStandardCloudError(Exception):
    """Raised when a cloud request fails."""

    def __init__(self, code: int, message: str) -> None:
        """Store the API code + message."""
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message


@dataclass(frozen=True)
class DeviceDetail:
    """Optional ``detail`` block from the deviceList response."""

    mode_list: list[str] = field(default_factory=list)
    speed_list: list[str] = field(default_factory=list)
    support_point_five: bool = False
    support_point_one: bool = False
    off_set_mode: bool = False
    dtype: str = ""
    model: str = ""


@dataclass(frozen=True)
class Device:
    """A device from the deviceList response."""

    id: str
    type: str
    name: str
    online: bool
    detail: DeviceDetail


@dataclass(frozen=True)
class DevState:
    """Parsed device state from the query response."""

    raw: dict[str, Any]
    pow: str = ""
    mode: str = ""
    speed: str = ""
    temperature: float | None = None
    tem_unit: str = "C"


@dataclass(frozen=True)
class QueryResult:
    """Per-device result of a query: online flag + parsed state.

    ``online`` comes from the query response itself and is fresher than the
    deviceList flag — the entity availability must prefer it.
    """

    online: bool
    state: DevState | None


def _parse_pipe_list(value: str | None) -> list[str]:
    """Split a pipe-separated string (``"s1|s2"``) into a list."""
    if not value:
        return []
    return [item for item in value.split("|") if item]


def _parse_detail(raw: dict[str, Any] | None) -> DeviceDetail:
    """Build a DeviceDetail from the raw ``detail`` dict."""
    raw = raw or {}
    return DeviceDetail(
        mode_list=_parse_pipe_list(raw.get("modeList")),
        speed_list=_parse_pipe_list(raw.get("speedList")),
        support_point_five=bool(raw.get("supportPointFive", 0)),
        support_point_one=bool(raw.get("supportPointOne", 0)),
        off_set_mode=bool(raw.get("offSetMode", 0)),
        dtype=raw.get("dType", "") or "",
        model=raw.get("model", "") or "",
    )


def _parse_temperature(state: dict[str, Any]) -> tuple[float | None, str]:
    """Return the reported temperature and unit."""
    base = state.get("temperature")
    unit = state.get("temUnit", "C") or "C"
    if base is None:
        return None, unit
    try:
        temp = float(base)
    except ValueError, TypeError:
        return None, unit
    if unit == "C" and state.get("addPointFiveValue"):
        temp += 0.5
    return temp, unit


def _parse_state(raw: dict[str, Any] | None) -> DevState | None:
    """Build a DevState from a query ``state`` dict; None if absent."""
    if not raw:
        return None
    temp, unit = _parse_temperature(raw)
    return DevState(
        raw=dict(raw),
        pow=raw.get("pow", "") or "",
        mode=raw.get("mode", "") or "",
        speed=raw.get("speed", "") or "",
        temperature=temp,
        tem_unit=unit,
    )


class GRStandardCloud:
    """Cloud API client."""

    def __init__(
        self,
        session: ClientSession,
        access_token: str,
        region: str | None = None,
    ) -> None:
        """Initialize the cloud client."""
        self._session = session
        self._access_token = access_token
        self._host: OpenPlatformHost = get_openplatform_host(region)

    @property
    def access_token(self) -> str:
        """The current Bearer token."""
        return self._access_token

    @access_token.setter
    def access_token(self, value: str) -> None:
        """Replace the Bearer token in place (called after refresh)."""
        self._access_token = value

    @property
    def base_url(self) -> str:
        """The ``https://<host>`` base for this region."""
        return f"https://{self._host.host}"

    async def _post(self, namespace: str, payload: dict[str, Any] | None = None) -> Any:
        """Send a cloud request and return its data."""
        url = f"{self.base_url}{_SMARTHOME_PATH}"
        body: dict[str, Any] = {
            "requestId": uuid.uuid4().hex,
            "timestamp": int(time.time() * 1000),
            "namespace": namespace,
        }
        if payload is not None:
            body["payload"] = payload
        # Keep serialization stable for request signing.
        body_str = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
        sign = hashlib.md5((body_str + OP_CLIENT_SECRET).encode()).hexdigest().upper()
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "appid": OP_CLIENT_ID,
            "sign": sign,
            "Content-Type": "application/json",
        }
        try:
            async with self._session.post(
                url, data=body_str.encode(), headers=headers, timeout=_REQUEST_TIMEOUT
            ) as resp:
                if resp.status != 200:
                    raise GreeStandardCloudError(resp.status, "HTTP error")
                result = await resp.json()
        except ClientError as err:
            raise GreeStandardCloudError(-1, f"request failed: {err}") from err

        code = result.get("code", 0)
        if code != 200:
            raise GreeStandardCloudError(code, result.get("message", ""))
        return result.get("data")

    async def get_devices(self) -> list[Device]:
        """Return supported devices."""
        data = await self._post("deviceList")
        devices: list[Device] = []
        for item in data or []:
            dtype = item.get("type", "")
            if dtype not in ("ac", "multiAc"):
                continue
            devices.append(
                Device(
                    id=item["id"],
                    type=dtype,
                    name=item.get("name", ""),
                    online=bool(item.get("online", False)),
                    detail=_parse_detail(item.get("detail")),
                )
            )
        return devices

    async def query(self, device_ids: list[str]) -> dict[str, QueryResult]:
        """Return the current state of the requested devices."""
        if not device_ids:
            return {}
        data = await self._post(
            "query",
            {"devices": [{"id": dev_id} for dev_id in device_ids]},
        )
        result: dict[str, QueryResult] = {}
        for dev_id, dev_data in (data or {}).items():
            if not isinstance(dev_data, dict):
                result[dev_id] = QueryResult(online=False, state=None)
                continue
            result[dev_id] = QueryResult(
                online=bool(dev_data.get("online", False)),
                state=_parse_state(dev_data.get("state")),
            )
        return result

    async def control(self, device_id: str, cmd: dict[str, Any]) -> None:
        """Send a control command to one device."""
        data = await self._post(
            "singleDeviceControl",
            {"id": device_id, "cmd": cmd},
        )
        dev_result = (data or {}).get(device_id, {}) if isinstance(data, dict) else {}
        if not dev_result.get("done", False):
            raise GreeStandardCloudError(
                dev_result.get("error", -1)
                if dev_result.get("error") is not None
                else -1,
                dev_result.get("message", "control failed"),
            )
