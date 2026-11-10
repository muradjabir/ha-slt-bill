"""Sensor platform for SLT Bill and Broadband integration."""
from __future__ import annotations

from datetime import date, datetime
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfInformation
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SLTBillCoordinator

_LOGGER = logging.getLogger(__name__)


def parse_date(date_str: str | None) -> date | None:
    """Parse date string formatted as YYYY/MM/DD or YYYY-MM-DD into a date object."""
    if not date_str:
        return None
    try:
        clean = date_str.strip().replace("-", "/")
        return datetime.strptime(clean, "%Y/%m/%d").date()
    except (ValueError, TypeError):
        return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the SLT sensors from config entry."""
    coordinator: SLTBillCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = []

    if coordinator.data:
        for conn_key, conn_data in coordinator.data.items():
            entities.extend(
                [
                    SLTOutstandingBalanceSensor(coordinator, conn_key),
                    SLTLastBillAmountSensor(coordinator, conn_key),
                    SLTLastPaymentAmountSensor(coordinator, conn_key),
                    SLTPaymentDueDateSensor(coordinator, conn_key),
                    SLTLastBillDateSensor(coordinator, conn_key),
                    SLTLastPaymentDateSensor(coordinator, conn_key),
                    SLTConnectionStatusSensor(coordinator, conn_key),
                ]
            )

            # Add broadband sensors if broadband service is present
            if conn_data.get("has_broadband"):
                entities.append(SLTBroadbandDataUsedSensor(coordinator, conn_key))
                entities.append(SLTBroadbandPackageSensor(coordinator, conn_key))
                if conn_data.get("data_limit") is not None:
                    entities.append(
                        SLTBroadbandDataRemainingSensor(coordinator, conn_key)
                    )

    async_add_entities(entities)


class SLTBaseSensor(CoordinatorEntity[SLTBillCoordinator], SensorEntity):
    """Base sensor for SLT connection entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: SLTBillCoordinator, conn_key: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._conn_key = conn_key

    @property
    def conn_data(self) -> dict[str, Any]:
        """Return the connection data dictionary."""
        if not self.coordinator.data:
            return {}
        return self.coordinator.data.get(self._conn_key, {})

    @property
    def available(self) -> bool:
        """Return True if coordinator data is available and contains connection."""
        return self.coordinator.last_update_success and bool(self.conn_data)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information linking all entities for this telephone connection."""
        acc_no = self.conn_data.get("account_number", "")
        tp_no = self.conn_data.get("telephone_number", "")
        promo_name = self.conn_data.get("promotion_name") or "SLT Connection"

        return DeviceInfo(
            identifiers={(DOMAIN, self._conn_key)},
            name=f"SLT {tp_no} ({acc_no})",
            manufacturer="Sri Lanka Telecom (SLT-Mobitel)",
            model=promo_name,
            configuration_url="https://myslt.slt.lk/",
        )


class SLTOutstandingBalanceSensor(SLTBaseSensor):
    """Sensor for outstanding bill balance."""

    _attr_translation_key = "outstanding_balance"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = "LKR"
    _attr_icon = "mdi:cash-multiple"
    _unrecorded_attributes = frozenset({"customer_name"})

    def __init__(self, coordinator: SLTBillCoordinator, conn_key: str) -> None:
        """Initialize."""
        super().__init__(coordinator, conn_key)
        self._attr_unique_id = f"slt_{conn_key}_outstanding_balance"

    @property
    def native_value(self) -> float | None:
        """Return outstanding balance."""
        return self.conn_data.get("outstanding_balance")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return detailed state attributes."""
        return {
            "account_number": self.conn_data.get("account_number"),
            "telephone_number": self.conn_data.get("telephone_number"),
            "customer_name": self.conn_data.get("customer_name"),
            "promotion_name": self.conn_data.get("promotion_name"),
            "promotion_type": self.conn_data.get("promotion_type"),
            "status": self.conn_data.get("status"),
            "last_bill_amount": self.conn_data.get("bill_amount"),
            "last_bill_date": self.conn_data.get("last_bill_date"),
            "payment_due_date": self.conn_data.get("payment_due_date"),
            "last_payment_date": self.conn_data.get("last_payment_date"),
            "last_payment_amount": self.conn_data.get("last_payment_amount"),
            "last_synced": self.conn_data.get("last_synced"),
        }


class SLTLastBillAmountSensor(SLTBaseSensor):
    """Sensor for latest bill invoice amount."""

    _attr_translation_key = "last_bill_amount"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = "LKR"
    _attr_icon = "mdi:receipt-text-outline"

    def __init__(self, coordinator: SLTBillCoordinator, conn_key: str) -> None:
        """Initialize."""
        super().__init__(coordinator, conn_key)
        self._attr_unique_id = f"slt_{conn_key}_last_bill_amount"

    @property
    def native_value(self) -> float | None:
        """Return bill amount."""
        return self.conn_data.get("bill_amount")


class SLTLastPaymentAmountSensor(SLTBaseSensor):
    """Sensor for last payment received."""

    _attr_translation_key = "last_payment_amount"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = "LKR"
    _attr_icon = "mdi:cash-check"

    def __init__(self, coordinator: SLTBillCoordinator, conn_key: str) -> None:
        """Initialize."""
        super().__init__(coordinator, conn_key)
        self._attr_unique_id = f"slt_{conn_key}_last_payment_amount"

    @property
    def native_value(self) -> float | None:
        """Return last payment amount."""
        return self.conn_data.get("last_payment_amount")


class SLTPaymentDueDateSensor(SLTBaseSensor):
    """Sensor for bill payment due date."""

    _attr_translation_key = "payment_due_date"
    _attr_device_class = SensorDeviceClass.DATE
    _attr_icon = "mdi:calendar-clock"

    def __init__(self, coordinator: SLTBillCoordinator, conn_key: str) -> None:
        """Initialize."""
        super().__init__(coordinator, conn_key)
        self._attr_unique_id = f"slt_{conn_key}_payment_due_date"

    @property
    def native_value(self) -> date | None:
        """Return payment due date as a date object."""
        return parse_date(self.conn_data.get("payment_due_date"))


class SLTLastBillDateSensor(SLTBaseSensor):
    """Sensor for last bill issue date."""

    _attr_translation_key = "last_bill_date"
    _attr_device_class = SensorDeviceClass.DATE
    _attr_icon = "mdi:calendar-text"

    def __init__(self, coordinator: SLTBillCoordinator, conn_key: str) -> None:
        """Initialize."""
        super().__init__(coordinator, conn_key)
        self._attr_unique_id = f"slt_{conn_key}_last_bill_date"

    @property
    def native_value(self) -> date | None:
        """Return last bill date as a date object."""
        return parse_date(self.conn_data.get("last_bill_date"))


class SLTLastPaymentDateSensor(SLTBaseSensor):
    """Sensor for date of the last payment made."""

    _attr_translation_key = "last_payment_date"
    _attr_device_class = SensorDeviceClass.DATE
    _attr_icon = "mdi:calendar-check"

    def __init__(self, coordinator: SLTBillCoordinator, conn_key: str) -> None:
        """Initialize."""
        super().__init__(coordinator, conn_key)
        self._attr_unique_id = f"slt_{conn_key}_last_payment_date"

    @property
    def native_value(self) -> date | None:
        """Return last payment date as a date object."""
        return parse_date(self.conn_data.get("last_payment_date"))


class SLTConnectionStatusSensor(SLTBaseSensor):
    """Sensor for SLT connection active status."""

    _attr_translation_key = "connection_status"
    _attr_icon = "mdi:network-outline"

    def __init__(self, coordinator: SLTBillCoordinator, conn_key: str) -> None:
        """Initialize."""
        super().__init__(coordinator, conn_key)
        self._attr_unique_id = f"slt_{conn_key}_status"

    @property
    def native_value(self) -> str | None:
        """Return status string (e.g. ACTIVE)."""
        return self.conn_data.get("status")


class SLTBroadbandDataUsedSensor(SLTBaseSensor):
    """Sensor for broadband data used."""

    _attr_translation_key = "broadband_data_used"
    _attr_device_class = SensorDeviceClass.DATA_SIZE
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = UnitOfInformation.GIGABYTES
    _attr_icon = "mdi:download-network"

    def __init__(self, coordinator: SLTBillCoordinator, conn_key: str) -> None:
        """Initialize."""
        super().__init__(coordinator, conn_key)
        self._attr_unique_id = f"slt_{conn_key}_data_used"

    @property
    def native_value(self) -> float | None:
        """Return total used data in GB."""
        return self.conn_data.get("data_used")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return broadband usage attributes."""
        return {
            "package_name": self.conn_data.get("broadband_package"),
            "data_limit": self.conn_data.get("data_limit"),
            "data_remaining": self.conn_data.get("data_remaining"),
            "billing_cycle_expiry": self.conn_data.get("billing_cycle_expiry"),
            "usage_status": self.conn_data.get("usage_status"),
        }


class SLTBroadbandPackageSensor(SLTBaseSensor):
    """Sensor for broadband subscription package name."""

    _attr_translation_key = "broadband_package"
    _attr_icon = "mdi:package-variant-closed"

    def __init__(self, coordinator: SLTBillCoordinator, conn_key: str) -> None:
        """Initialize."""
        super().__init__(coordinator, conn_key)
        self._attr_unique_id = f"slt_{conn_key}_package"

    @property
    def native_value(self) -> str | None:
        """Return package name (e.g. UNLIMITED HOME)."""
        return self.conn_data.get("broadband_package")


class SLTBroadbandDataRemainingSensor(SLTBaseSensor):
    """Sensor for remaining broadband quota (for capped plans)."""

    _attr_translation_key = "broadband_data_remaining"
    _attr_device_class = SensorDeviceClass.DATA_SIZE
    _attr_native_unit_of_measurement = UnitOfInformation.GIGABYTES
    _attr_icon = "mdi:gauge"

    def __init__(self, coordinator: SLTBillCoordinator, conn_key: str) -> None:
        """Initialize."""
        super().__init__(coordinator, conn_key)
        self._attr_unique_id = f"slt_{conn_key}_data_remaining"

    @property
    def native_value(self) -> float | None:
        """Return remaining data in GB."""
        return self.conn_data.get("data_remaining")

