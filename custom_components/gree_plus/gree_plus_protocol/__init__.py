"""Gree Plus cloud protocol SDK (vendored sub-package).

Two clients for the Gree open platform:

- :class:`GROauthControl` — OAuth2 authorization-code flow (authorize URL,
  code→token exchange, refresh, userInfo).
- :class:`GRStandardCloud` — standard-cloud device API (deviceList / query /
  singleDeviceControl), the operational client used by the coordinator.

The HA shared aiohttp ClientSession is injected into both clients.

Usage (from within the integration)::

    from .gree_plus_protocol import (
        GROauthControl,
        GRStandardCloud,
        TokenInfo,
        UserInfo,
    )
"""

from .GRConst import OP_CLIENT_ID, OP_CLIENT_SECRET
from .GROauthControl import (
    GreeOAuthError,
    GROauthControl,
    OAuthInteractionRequired,
    OpenPlatformHost,
    TokenInfo,
    UserInfo,
    available_regions,
    get_openplatform_host,
)
from .GRStandardCloud import (
    Device,
    DeviceDetail,
    DevState,
    GreeStandardCloudError,
    GRStandardCloud,
    QueryResult,
)

__all__ = [
    "OP_CLIENT_ID",
    "OP_CLIENT_SECRET",
    "DevState",
    "Device",
    "DeviceDetail",
    "GROauthControl",
    "GRStandardCloud",
    "GreeOAuthError",
    "GreeStandardCloudError",
    "OAuthInteractionRequired",
    "OpenPlatformHost",
    "QueryResult",
    "TokenInfo",
    "UserInfo",
    "available_regions",
    "get_openplatform_host",
]
