"""Config flow for SLT Bill integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, selector

from .api import SLTApi, SLTAuthError, SLTConnectionError, SLTError
from .const import (
    DOMAIN,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL_HOURS,
    CONF_SELECTED_CONNECTIONS,
    DEFAULT_SCAN_INTERVAL_HOURS,
    MIN_SCAN_INTERVAL_HOURS,
)

_LOGGER = logging.getLogger(__name__)


def validate_slt_credentials(username: str, password: str) -> list[dict[str, Any]]:
    """Validate credentials and fetch accounts synchronously."""
    api = SLTApi(username, password)
    api.login()
    accounts = api.get_accounts()
    if not accounts:
        raise NoConnectionsFound
    return accounts


class SLTConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SLT Bill."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._auth_data: dict[str, Any] = {}
        self._discovered_accounts: list[dict[str, Any]] = []

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get options flow for this handler."""
        return SLTOptionsFlowHandler()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial authentication step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            username = user_input[CONF_USERNAME].strip()
            password = user_input[CONF_PASSWORD].strip()

            await self.async_set_unique_id(username.lower())
            self._abort_if_unique_id_configured()

            try:
                accounts = await self.hass.async_add_executor_job(
                    validate_slt_credentials, username, password
                )
            except SLTAuthError:
                errors["base"] = "invalid_auth"
            except SLTConnectionError:
                errors["base"] = "cannot_connect"
            except NoConnectionsFound:
                errors["base"] = "no_connections"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception in SLT config flow")
                errors["base"] = "unknown"
            else:
                self._auth_data = {
                    CONF_USERNAME: username,
                    CONF_PASSWORD: password,
                    CONF_SCAN_INTERVAL_HOURS: user_input.get(
                        CONF_SCAN_INTERVAL_HOURS, DEFAULT_SCAN_INTERVAL_HOURS
                    ),
                }
                self._discovered_accounts = accounts

                if len(accounts) == 1:
                    first = accounts[0]
                    conn_key = f"{first.get('accountno')}_{first.get('telephoneno')}"
                    self._auth_data[CONF_SELECTED_CONNECTIONS] = [conn_key]
                    return self.async_create_entry(
                        title=f"SLT {first.get('telephoneno')}",
                        data=self._auth_data,
                    )

                return await self.async_step_connections()

        schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): selector.TextSelector(
                    selector.TextSelectorConfig(
                        type=selector.TextSelectorType.PASSWORD
                    )
                ),
                vol.Optional(
                    CONF_SCAN_INTERVAL_HOURS, default=DEFAULT_SCAN_INTERVAL_HOURS
                ): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL_HOURS)),
            }
        )

        return self.async_show_form(
            step_id="user", data_schema=schema, errors=errors
        )

    async def async_step_connections(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Select which connections under the account to track."""
        errors: dict[str, str] = {}

        options = {
            f"{acc.get('accountno')}_{acc.get('telephoneno')}": (
                f"{acc.get('telephoneno')} (Account: {acc.get('accountno')})"
            )
            for acc in self._discovered_accounts
        }

        if user_input is not None:
            selected = user_input.get(CONF_SELECTED_CONNECTIONS, [])
            if not selected:
                errors[CONF_SELECTED_CONNECTIONS] = "must_select_connection"
            else:
                self._auth_data[CONF_SELECTED_CONNECTIONS] = selected
                username = self._auth_data[CONF_USERNAME]
                return self.async_create_entry(
                    title=f"SLT ({username})",
                    data=self._auth_data,
                )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SELECTED_CONNECTIONS,
                    default=list(options.keys()),
                ): cv.multi_select(options)
            }
        )

        return self.async_show_form(
            step_id="connections", data_schema=schema, errors=errors
        )


class SLTOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for SLT Bill integration."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage integration options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL_HOURS,
            self.config_entry.data.get(
                CONF_SCAN_INTERVAL_HOURS, DEFAULT_SCAN_INTERVAL_HOURS
            ),
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SCAN_INTERVAL_HOURS,
                        default=current_interval,
                    ): vol.All(vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL_HOURS)),
                }
            ),
        )


class NoConnectionsFound(HomeAssistantError):
    """Error to indicate no connections found for this account."""

