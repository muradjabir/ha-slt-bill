"""DataUpdateCoordinator for the SLT Bill integration."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SLTApi, SLTAuthError, SLTConnectionError, SLTError
from .const import DEFAULT_SCAN_INTERVAL_HOURS

_LOGGER = logging.getLogger(__name__)


def sync_fetch_slt_data(
    api: SLTApi,
    selected_connections: list[str] | None,
) -> dict[str, dict[str, Any]]:
    """Fetch data synchronously from SLT API for all selected connections."""
    accounts = api.get_accounts()
    result: dict[str, dict[str, Any]] = {}

    for acc in accounts:
        acc_no = str(acc.get("accountno", "")).strip()
        tp_no = str(acc.get("telephoneno", "")).strip()
        status = str(acc.get("status", "ACTIVE")).strip()

        conn_key = f"{acc_no}_{tp_no}"

        # If user specified a subset of connections, filter accordingly
        if selected_connections and conn_key not in selected_connections:
            continue

        try:
            conn_data = api.fetch_connection_data(acc_no, tp_no, status)
            result[conn_key] = conn_data
        except Exception as err:
            _LOGGER.warning(
                "Failed to fetch data for connection %s (%s): %s",
                tp_no,
                acc_no,
                err,
            )

    if not result:
        raise UpdateFailed("No data could be retrieved for configured SLT connections.")

    return result


class SLTBillCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Class to manage fetching SLT bill and broadband data."""

    def __init__(
        self,
        hass: HomeAssistant,
        username: str,
        password: str,
        selected_connections: list[str] | None = None,
        scan_interval_hours: int = DEFAULT_SCAN_INTERVAL_HOURS,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"SLT Bill ({username})",
            update_interval=timedelta(hours=scan_interval_hours),
        )
        self.api = SLTApi(username, password)
        self.selected_connections = selected_connections

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        """Fetch data from SLT API in executor."""
        try:
            return await self.hass.async_add_executor_job(
                sync_fetch_slt_data,
                self.api,
                self.selected_connections,
            )
        except SLTAuthError as err:
            raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
        except SLTConnectionError as err:
            raise UpdateFailed(f"Error communicating with SLT API: {err}") from err
        except SLTError as err:
            raise UpdateFailed(f"SLT data error: {err}") from err
        except Exception as err:
            raise UpdateFailed(f"Unexpected error: {err}") from err

