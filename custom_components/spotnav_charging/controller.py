"""Persistent charging schedule and charger control."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import CONF_CHARGE_CONTROL, CONF_CURRENT_LIMIT, DOMAIN

_LOGGER = logging.getLogger(__name__)
STORE_VERSION = 1


@dataclass(slots=True)
class ChargingPlan:
    """A charging period received from SpotNav."""

    start: str
    end: str
    amps: int
    phases: int = 3
    power_kw: float | None = None
    energy_kwh: float | None = None
    price_area: str | None = None
    estimated: bool = False
    periods: list[dict[str, str]] | None = None

    @property
    def start_time(self) -> datetime:
        return _parse_datetime(self.start)

    @property
    def end_time(self) -> datetime:
        return _parse_datetime(self.end)

    @property
    def windows(self) -> list[tuple[datetime, datetime]]:
        if not self.periods:
            return [(self.start_time, self.end_time)]
        return [(_parse_datetime(item["start"]), _parse_datetime(item["end"])) for item in self.periods]


def _parse_datetime(value: str) -> datetime:
    parsed = dt_util.parse_datetime(value)
    if parsed is None or parsed.tzinfo is None:
        raise ValueError("Timestamp must include a time zone")
    return parsed


class ChargingController:
    """Control one Home Assistant charger from SpotNav commands."""

    def __init__(self, hass: HomeAssistant, entry_id: str, config: dict[str, Any]) -> None:
        self.hass = hass
        self.entry_id = entry_id
        self.charge_control: str = config[CONF_CHARGE_CONTROL]
        self.current_limit: str | None = config.get(CONF_CURRENT_LIMIT) or None
        self.plan: ChargingPlan | None = None
        self._store: Store[dict[str, Any]] = Store(
            hass, STORE_VERSION, f"{DOMAIN}.{entry_id}"
        )
        self._timer_cancels: list[Callable[[], None]] = []
        self._listeners: set[Callable[[], None]] = set()

    async def async_initialize(self) -> None:
        """Restore a saved schedule and resume it."""
        saved = await self._store.async_load()
        if saved and saved.get("plan"):
            try:
                self.plan = ChargingPlan(**saved["plan"])
            except (TypeError, ValueError):
                _LOGGER.warning("Discarding invalid saved SpotNav charging plan")
        await self._async_reschedule()

    async def async_schedule(self, payload: dict[str, Any]) -> None:
        """Validate, store and activate a new charging schedule."""
        periods = payload.get("periods") or [{"start": payload["start"], "end": payload["end"]}]
        if not isinstance(periods, list) or not 1 <= len(periods) <= 8:
            raise ValueError("Schedule must contain between one and eight periods")
        normalized_periods = [{"start": str(item["start"]), "end": str(item["end"])} for item in periods]
        plan = ChargingPlan(
            start=normalized_periods[0]["start"],
            end=normalized_periods[-1]["end"],
            amps=int(payload["amps"]),
            phases=int(payload.get("phases", 3)),
            power_kw=_optional_float(payload.get("power_kw")),
            energy_kwh=_optional_float(payload.get("energy_kwh")),
            price_area=payload.get("price_area"),
            estimated=bool(payload.get("estimated", False)),
            periods=normalized_periods,
        )
        previous_end: datetime | None = None
        for start, end in plan.windows:
            if end <= start:
                raise ValueError("Period end must be after its start")
            if previous_end is not None and start < previous_end:
                raise ValueError("Charging periods must be ordered and must not overlap")
            previous_end = end
        if plan.end_time <= dt_util.utcnow():
            raise ValueError("End time must be in the future")
        if plan.end_time > dt_util.utcnow() + timedelta(days=7):
            raise ValueError("End time must be within seven days")
        self._validate_amps(plan.amps)
        self.plan = plan
        await self._async_save()
        await self._async_reschedule()
        self._notify()

    async def async_cancel(self) -> None:
        """Stop charging and remove the active schedule."""
        await self.async_stop(clear_schedule=True)

    async def async_follow_schedule(self) -> None:
        """Immediately restore the charger state required by the saved plan."""
        if self.plan is None:
            raise HomeAssistantError("No charging schedule is active")
        await self._async_reschedule()

    async def async_start(self, amps: int | None = None) -> None:
        """Apply the requested current and start charging."""
        requested_amps = amps if amps is not None else self.plan.amps if self.plan else None
        if requested_amps is not None:
            self._validate_amps(requested_amps)
            if self.current_limit:
                await self.hass.services.async_call(
                    "number",
                    "set_value",
                    {"entity_id": self.current_limit, "value": requested_amps},
                    blocking=True,
                )
        if not self.charging:
            await self.hass.services.async_call(
                "switch", "turn_on", {"entity_id": self.charge_control}, blocking=True
            )
        self._notify()

    async def async_stop(self, *, clear_schedule: bool = False) -> None:
        """Stop charging, optionally removing the saved schedule."""
        if self.charging:
            await self.hass.services.async_call(
                "switch", "turn_off", {"entity_id": self.charge_control}, blocking=True
            )
        if clear_schedule:
            self.plan = None
            self._cancel_timers()
            await self._async_save()
        self._notify()

    async def async_shutdown(self) -> None:
        """Cancel local callbacks without changing the charger."""
        self._cancel_timers()

    @property
    def charging(self) -> bool:
        state = self.hass.states.get(self.charge_control)
        return state is not None and state.state == STATE_ON

    def add_listener(self, listener: Callable[[], None]) -> Callable[[], None]:
        self._listeners.add(listener)
        return lambda: self._listeners.discard(listener)

    @callback
    def _notify(self) -> None:
        for listener in self._listeners:
            listener()

    def _validate_amps(self, amps: int) -> None:
        if amps < 1 or amps > 80:
            raise ValueError("Charging current is outside the supported range")
        if not self.current_limit:
            return
        state = self.hass.states.get(self.current_limit)
        if state is None:
            return
        minimum = float(state.attributes.get("min", 0))
        maximum = float(state.attributes.get("max", 80))
        if not minimum <= amps <= maximum:
            raise ValueError(f"Charging current must be between {minimum:g} and {maximum:g} A")

    async def _async_save(self) -> None:
        await self._store.async_save({"plan": asdict(self.plan) if self.plan else None})

    async def _async_reschedule(self) -> None:
        self._cancel_timers()
        if self.plan is None:
            return
        now = dt_util.utcnow()
        windows = self.plan.windows
        if now >= windows[-1][1]:
            await self.async_stop(clear_schedule=True)
            return
        active = any(start <= now < end for start, end in windows)
        if active:
            await self.async_start()
        else:
            await self.async_stop(clear_schedule=False)
        for index, (start, end) in enumerate(windows):
            if start > now:
                self._timer_cancels.append(async_track_point_in_utc_time(
                    self.hass, self._async_start_callback, start
                ))
            if end > now:
                final = index == len(windows) - 1
                self._timer_cancels.append(async_track_point_in_utc_time(
                    self.hass, lambda event_time, is_final=final: self._async_end_callback(event_time, is_final), end
                ))

    @callback
    def _async_start_callback(self, _now: datetime) -> None:
        self.hass.async_create_task(self.async_start())

    @callback
    def _async_end_callback(self, _now: datetime, final: bool) -> None:
        self.hass.async_create_task(self.async_stop(clear_schedule=final))

    def _cancel_timers(self) -> None:
        for cancel in self._timer_cancels:
            cancel()
        self._timer_cancels.clear()


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)
