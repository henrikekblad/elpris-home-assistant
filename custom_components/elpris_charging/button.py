"""Control buttons for Elpris charging control."""

from collections.abc import Awaitable, Callable

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .controller import ChargingController
from .entity import ElprisChargingEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    controller: ChargingController = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            ControlButton(entry, controller, "start", controller.async_start),
            ControlButton(entry, controller, "stop", controller.async_stop),
            ControlButton(entry, controller, "follow", controller.async_follow_schedule),
            ControlButton(entry, controller, "cancel", controller.async_cancel),
        ]
    )


class ControlButton(ElprisChargingEntity, ButtonEntity):
    """Run one charger command."""

    def __init__(
        self,
        entry: ConfigEntry,
        controller: ChargingController,
        key: str,
        action: Callable[[], Awaitable[None]],
    ) -> None:
        super().__init__(entry, controller)
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._key = key
        self._action = action

    @property
    def available(self) -> bool:
        """The follow action requires an existing charging plan."""
        return self._key != "follow" or self.controller.plan is not None

    async def async_press(self) -> None:
        await self._action()
