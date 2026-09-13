"""Schedule and connection sensors for Elpris charging control."""

from datetime import datetime
from urllib.parse import urlencode

from homeassistant.components import webhook
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.network import NoURLAvailableError

from .const import CONF_WEBHOOK_ID, DOMAIN
from .controller import ChargingController
from .entity import ElprisChargingEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    controller: ChargingController = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            ConnectionEntity(hass, entry, controller),
            PlanTimeEntity(entry, controller, "start"),
            PlanTimeEntity(entry, controller, "end"),
        ]
    )


class ConnectionEntity(ElprisChargingEntity, SensorEntity):
    """Expose pairing data to the Home Assistant owner."""

    _attr_translation_key = "connection"
    _attr_native_value = "ready"

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, controller: ChargingController
    ) -> None:
        super().__init__(entry, controller)
        self._hass = hass
        self._attr_unique_id = f"{entry.entry_id}_connection"

    @property
    def extra_state_attributes(self) -> dict[str, str]:
        webhook_id = self._entry.data[CONF_WEBHOOK_ID]
        try:
            webhook_url = webhook.async_generate_url(
                self._hass, webhook_id, allow_internal=True, prefer_external=True
            )
            base_url = webhook_url.rsplit("/api/webhook/", 1)[0]
        except NoURLAvailableError:
            base_url = ""
            webhook_url = webhook.async_generate_path(webhook_id)
        pairing_query = urlencode({"url": base_url, "webhook": webhook_id})
        return {
            "home_assistant_url": base_url,
            "webhook_id": webhook_id,
            "webhook_url": webhook_url,
            "pairing_uri": f"elpris://home-assistant?{pairing_query}",
        }


class PlanTimeEntity(ElprisChargingEntity, SensorEntity):
    """Start or end of the current charging plan."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(
        self, entry: ConfigEntry, controller: ChargingController, point: str
    ) -> None:
        super().__init__(entry, controller)
        self._point = point
        self._attr_unique_id = f"{entry.entry_id}_{point}"
        self._attr_translation_key = f"plan_{point}"

    @property
    def native_value(self) -> datetime | None:
        if self.controller.plan is None:
            return None
        return (
            self.controller.plan.start_time
            if self._point == "start"
            else self.controller.plan.end_time
        )
