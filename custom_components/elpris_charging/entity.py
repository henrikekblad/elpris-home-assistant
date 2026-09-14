"""Base entity for SpotNav charging control."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .controller import ChargingController


class SpotNavChargingEntity(Entity):
    """Entity backed by the SpotNav charging controller."""

    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry, controller: ChargingController) -> None:
        self._entry = entry
        self.controller = controller
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Sensnology",
            model="SpotNav charging control",
        )

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.controller.add_listener(self.async_write_ha_state))
