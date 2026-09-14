"""Config flow for SpotNav charging control."""

from __future__ import annotations

import secrets
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import entity_registry as er, selector

from .const import (
    CONF_CHARGE_CONTROL,
    CONF_CURRENT_LIMIT,
    CONF_MODE,
    CONF_WEBHOOK_ID,
    DOMAIN,
    MODE_GENERIC,
    MODE_OCPP,
)


class SpotNavChargingConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure SpotNav charging control."""

    VERSION = 1

    def __init__(self) -> None:
        self._mode = MODE_OCPP
        self._device_id: str | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Choose OCPP discovery or generic Home Assistant entities."""
        if user_input is not None:
            self._mode = user_input[CONF_MODE]
            if self._mode == MODE_OCPP:
                return await self.async_step_ocpp_device()
            return await self.async_step_generic()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_MODE, default=MODE_OCPP): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[MODE_OCPP, MODE_GENERIC],
                            translation_key="mode",
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    )
                }
            ),
        )

    async def async_step_ocpp_device(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Select an OCPP device before presenting its entities."""
        if user_input is not None:
            self._device_id = user_input["device"]
            return await self.async_step_ocpp_entities()
        return self.async_show_form(
            step_id="ocpp_device",
            data_schema=vol.Schema(
                {
                    vol.Required("device"): selector.DeviceSelector(
                        selector.DeviceSelectorConfig(integration="ocpp")
                    )
                }
            ),
        )

    async def async_step_ocpp_entities(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Select only suitable entities belonging to the chosen OCPP device."""
        switches, numbers = self._entities_for_device(self._device_id)
        if not switches:
            return self.async_abort(reason="no_charge_control")
        if user_input is not None:
            return self._create_entry(user_input)
        schema: dict[Any, Any] = {
            vol.Required(CONF_CHARGE_CONTROL): vol.In(self._options(switches))
        }
        if numbers:
            schema[vol.Optional(CONF_CURRENT_LIMIT)] = vol.In(self._options(numbers))
        return self.async_show_form(step_id="ocpp_entities", data_schema=vol.Schema(schema))

    async def async_step_generic(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Select generic Home Assistant switch and number entities."""
        if user_input is not None:
            return self._create_entry(user_input)
        return self.async_show_form(
            step_id="generic",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CHARGE_CONTROL): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="switch")
                    ),
                    vol.Optional(CONF_CURRENT_LIMIT): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="number")
                    ),
                }
            ),
        )

    def _create_entry(self, user_input: dict[str, Any]) -> FlowResult:
        charge_control = user_input[CONF_CHARGE_CONTROL]
        state = self.hass.states.get(charge_control)
        title = state.name if state else charge_control
        return self.async_create_entry(
            title=title,
            data={
                CONF_MODE: self._mode,
                CONF_CHARGE_CONTROL: charge_control,
                CONF_CURRENT_LIMIT: user_input.get(CONF_CURRENT_LIMIT, ""),
                CONF_WEBHOOK_ID: secrets.token_urlsafe(32),
            },
        )

    def _entities_for_device(self, device_id: str | None) -> tuple[list[str], list[str]]:
        registry = er.async_get(self.hass)
        entries = er.async_entries_for_device(registry, device_id) if device_id else []
        all_switches = sorted(
            entry.entity_id for entry in entries
            if entry.domain == "switch" and entry.platform == "ocpp" and entry.disabled_by is None
        )
        switches = [
            entity_id for entity_id in all_switches
            if entity_id.endswith("_charge_control")
        ] or all_switches
        numbers = sorted(
            entry.entity_id for entry in entries
            if entry.domain == "number"
            and entry.platform == "ocpp"
            and entry.disabled_by is None
            and self.hass.states.get(entry.entity_id) is not None
            and self.hass.states.get(entry.entity_id).attributes.get("unit_of_measurement") == "A"
        )
        return switches, numbers

    def _options(self, entity_ids: list[str]) -> dict[str, str]:
        return {
            entity_id: self.hass.states.get(entity_id).name
            if self.hass.states.get(entity_id)
            else entity_id
            for entity_id in entity_ids
        }

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return SpotNavChargingOptionsFlow(config_entry)


class SpotNavChargingOptionsFlow(config_entries.OptionsFlow):
    """Edit charger entity choices."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            self.hass.config_entries.async_update_entry(
                self._entry, data={**self._entry.data, **user_input}
            )
            return self.async_create_entry(title="", data={})
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_CHARGE_CONTROL,
                        default=self._entry.data[CONF_CHARGE_CONTROL],
                    ): selector.EntitySelector(selector.EntitySelectorConfig(domain="switch")),
                    vol.Optional(
                        CONF_CURRENT_LIMIT,
                        default=self._entry.data.get(CONF_CURRENT_LIMIT, ""),
                    ): selector.EntitySelector(selector.EntitySelectorConfig(domain="number")),
                }
            ),
        )
