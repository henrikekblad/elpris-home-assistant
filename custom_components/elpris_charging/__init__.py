"""SpotNav charging control integration."""

from __future__ import annotations

import logging
from typing import Any

from aiohttp import web
from homeassistant.components import webhook
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_WEBHOOK_ID, DOMAIN, PLATFORMS
from .controller import ChargingController

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SpotNav charging control from a config entry."""
    controller = ChargingController(hass, entry.entry_id, dict(entry.data))
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = controller

    async def async_handle_webhook(
        _hass: HomeAssistant, _webhook_id: str, request: web.Request
    ) -> web.Response:
        try:
            payload: dict[str, Any] = await request.json()
            if payload.get("version") != 1:
                raise ValueError("Unsupported payload version")
            action = payload.get("action")
            if action == "status":
                plan = controller.plan
                return web.json_response(
                    {
                        "ok": True,
                        "action": action,
                        "charging_enabled": controller.charging,
                        "schedule_active": plan is not None,
                        "start": plan.start if plan else None,
                        "end": plan.end if plan else None,
                        "amps": plan.amps if plan else None,
                        "periods": plan.periods if plan else None,
                    }
                )
            if action == "schedule":
                await controller.async_schedule(payload)
            elif action == "cancel":
                await controller.async_cancel()
            elif action == "start":
                amps = int(payload["amps"]) if "amps" in payload else None
                await controller.async_start(amps)
            elif action == "stop":
                await controller.async_stop()
            else:
                raise ValueError("Unsupported action")
        except (KeyError, TypeError, ValueError) as error:
            _LOGGER.warning("Rejected SpotNav webhook command: %s", error)
            return web.json_response({"ok": False, "error": str(error)}, status=400)
        except Exception:
            _LOGGER.exception("SpotNav charger command failed")
            return web.json_response({"ok": False, "error": "Charger command failed"}, status=502)
        return web.json_response({"ok": True, "action": action})

    webhook.async_register(
        hass,
        DOMAIN,
        "SpotNav charging control",
        entry.data[CONF_WEBHOOK_ID],
        async_handle_webhook,
        local_only=False,
        allowed_methods=("POST",),
    )
    await controller.async_initialize()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a SpotNav charging control entry."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    webhook.async_unregister(hass, entry.data[CONF_WEBHOOK_ID])
    controller: ChargingController = hass.data[DOMAIN].pop(entry.entry_id)
    await controller.async_shutdown()
    return True
