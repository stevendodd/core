"""Support for TTLock."""
from __future__ import annotations

from datetime import datetime
import time
from typing import Any

import requests
import voluptuous as vol

from homeassistant.components.lock import PLATFORM_SCHEMA, LockEntity
from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    ATTR_HW_VERSION,
    ATTR_LOCKED,
    ATTR_MODEL,
    ATTR_SW_VERSION,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_DOMAIN,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

ATTR_AUTO_LOCK_TIME = "autoLockTime"
ATTR_PASSAGE_MODE = "passageMode"
ATTR_PASSAGE_MODE_AUTO_UNLOCK = "passageModeAutoUnlock"
ATTR_SOUND_VOLUME = "soundVolume"
ATTR_TAMPER_ALERT = "tamperAlert"
ATTR_ACCESS_TOKEN = "accessToken"
ATTR_ACCESS_TOKEN_EXPIRY_TIME = "accessTokenExpiryTime"
ATTR_LAST_USER = "lastUser"
ATTR_LAST_ENTRY_TIME = "lastEntryTime"
CONF_LOCK_ID = "lockId"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_DOMAIN, default="euapi.ttlock.com"): cv.string,
        vol.Optional(CONF_NAME, default="TTLock"): cv.string,
        vol.Required(CONF_LOCK_ID): cv.string,
        vol.Required(CONF_CLIENT_ID): cv.string,
        vol.Required(CONF_CLIENT_SECRET): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }
)


def current_milli_time():
    """Return time millis."""
    return round(time.time() * 1000)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the TTLock platform."""
    domain = config.get(CONF_DOMAIN)
    client_id = config.get(CONF_CLIENT_ID)
    client_secret = config.get(CONF_CLIENT_SECRET)
    user = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    lock_id = config.get(CONF_LOCK_ID)
    name = config.get(CONF_NAME)

    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "username": user,
        "password": password,
    }
    response = requests.post(f"https://{domain}/oauth2/token", data, timeout=10)

    if response.status_code == 200:
        access_token = response.json()["access_token"]
        token_expiry_time = (
            int(response.json()["expires_in"]) * 1000 + current_milli_time() - 25000
        )

        add_entities(
            [
                TTLockDevice(
                    access_token,
                    token_expiry_time,
                    domain,
                    client_id,
                    client_secret,
                    user,
                    password,
                    lock_id,
                    name,
                )
            ],
            update_before_add=True,
        )


class TTLockDevice(LockEntity):
    """Representation of a TTLock device."""

    def __init__(
        self,
        access_token,
        token_expiry_time,
        domain,
        client_id,
        client_secret,
        user,
        password,
        lock_id,
        name,
    ) -> None:
        """Initialize the TTLock device."""
        self._access_token = access_token
        self._access_token_expiry_time = token_expiry_time
        self._domain = domain
        self._client_id = client_id
        self._client_secret = client_secret
        self._user = user
        self._password = password
        self._lock_id = lock_id
        self._nickname = name

        self._auto_lock_time = -1
        self._electric_quantity = -1
        self._firmware_revision: str | None = None
        self._hardware_revision: str | None = None
        self._lock_alias: str | None = None
        self._model_num: str | None = None
        self._passage_mode = -1
        self._passage_mode_auto_unlock = -1
        self._sound_volume = -1
        self._tamper_alert = -1
        self._last_user = ""
        self._last_entry_time: str | None = None
        self._is_locked = True
        self._responsive = False

    @property
    def name(self) -> str | None:
        """Return the name of the device."""
        return self._nickname

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._responsive

    @property
    def is_locked(self) -> bool:
        """Return True if the device is currently locked, else False."""
        return self._is_locked

    def get_token(self) -> None:
        """Refresh access token."""
        if current_milli_time() > self._access_token_expiry_time:

            data = {
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "username": self._user,
                "password": self._password,
            }
            response = requests.post(
                f"https://{self._domain}/oauth2/token", data, timeout=10
            )

            if response.status_code == 200:
                self._access_token = response.json()["access_token"]
                self._access_token_expiry_time = (
                    int(response.json()["expires_in"]) * 1000
                    + current_milli_time()
                    - 25000
                )

    def unlock(self, **kwargs: Any) -> None:
        """Unlock the device."""
        self.get_token()
        data = {
            "clientId": self._client_id,
            "accessToken": self._access_token,
            "lockId": self._lock_id,
            "date": current_milli_time(),
        }

        response = requests.post(
            f"https://{self._domain}/v3/lock/unlock", data, timeout=10
        )

        if response.status_code == 200:
            self._is_locked = False

    def lock(self, **kwargs: Any) -> None:
        """Lock the device."""
        self.get_token()
        data = {
            "clientId": self._client_id,
            "accessToken": self._access_token,
            "lockId": self._lock_id,
            "date": current_milli_time(),
        }

        response = requests.post(
            f"https://{self._domain}/v3/lock/lock", data, timeout=10
        )

        if response.status_code == 200:
            self._is_locked = True

    def update(self) -> None:
        """Update the internal state of the device."""
        response = requests.get(
            "https://{}/v3/lock/detail?clientId={}&accessToken={}&lockId={}&date={}".format(
                self._domain,
                self._client_id,
                self._access_token,
                self._lock_id,
                str(current_milli_time()),
            ),
            timeout=10,
        )

        if response.status_code == 200:
            self._lock_alias = response.json()["lockAlias"]
            self._responsive = True
            self._is_locked = True
            self._auto_lock_time = response.json()["autoLockTime"]
            self._electric_quantity = response.json()["electricQuantity"]
            self._firmware_revision = response.json()["firmwareRevision"]
            self._hardware_revision = response.json()["hardwareRevision"]
            self._model_num = response.json()["modelNum"]
            self._passage_mode = response.json()["passageMode"]
            self._passage_mode_auto_unlock = response.json()["passageModeAutoUnlock"]
            self._sound_volume = response.json()["soundVolume"]
            self._tamper_alert = response.json()["tamperAlert"]

            response = requests.get(
                "https://{}/v3/lock/queryOpenState?clientId={}&accessToken={}&lockId={}&date={}".format(
                    self._domain,
                    self._client_id,
                    self._access_token,
                    self._lock_id,
                    str(current_milli_time()),
                ),
                timeout=10,
            )

            if response.status_code == 200:
                if response.json()["state"] == 1:
                    self._is_locked = False

            response = requests.get(
                "https://{}/v3/lockRecord/list?clientId={}&accessToken={}&lockId={}&pageNo=1&pageSize=1&date={}".format(
                    self._domain,
                    self._client_id,
                    self._access_token,
                    self._lock_id,
                    str(current_milli_time()),
                ),
                timeout=10,
            )

            if response.status_code == 200:
                self._last_user = response.json()["list"][0]["username"]
                self._last_entry_time = datetime.fromtimestamp(
                    int(response.json()["list"][0]["lockDate"]) / 1000
                ).strftime("%a, %d %b %Y %H:%M")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return {
            ATTR_MODEL: self._model_num,
            ATTR_SW_VERSION: self._firmware_revision,
            ATTR_HW_VERSION: self._hardware_revision,
            ATTR_LOCKED: self._is_locked,
            ATTR_AUTO_LOCK_TIME: self._auto_lock_time,
            ATTR_PASSAGE_MODE: self._passage_mode,
            ATTR_PASSAGE_MODE_AUTO_UNLOCK: self._passage_mode_auto_unlock,
            ATTR_SOUND_VOLUME: self._sound_volume,
            ATTR_TAMPER_ALERT: self._tamper_alert,
            CONF_LOCK_ID: self._lock_id,
            ATTR_BATTERY_LEVEL: self._electric_quantity,
            ATTR_LAST_USER: self._last_user,
            ATTR_LAST_ENTRY_TIME: self._last_entry_time,
        }
