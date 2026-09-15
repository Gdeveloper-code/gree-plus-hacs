"""Constants for the gree_plus integration."""

from homeassistant.const import CONF_ACCESS_TOKEN, CONF_NAME, CONF_REGION

DOMAIN = "gree_plus"

# Config entry data keys (not exposed by homeassistant.const).
CONF_REFRESH_TOKEN = "refresh_token"
CONF_ACCESS_TOKEN_EXPIRES_AT = "access_token_expires_at"
CONF_REFRESH_TOKEN_ISSUED_AT = "refresh_token_issued_at"
CONF_OPEN_ID = "open_id"

__all__ = [
    "CONF_ACCESS_TOKEN",
    "CONF_ACCESS_TOKEN_EXPIRES_AT",
    "CONF_NAME",
    "CONF_OPEN_ID",
    "CONF_REFRESH_TOKEN",
    "CONF_REFRESH_TOKEN_ISSUED_AT",
    "CONF_REGION",
    "DOMAIN",
]
