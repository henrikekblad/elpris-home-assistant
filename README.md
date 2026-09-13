# Elpris charging control for Home Assistant

[![Open your Home Assistant instance and open this repository in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=henrikekblad&repository=elpris-home-assistant&category=integration)

Home Assistant integration for receiving and executing EV charging schedules from the [Elpris Android app](https://github.com/henrikekblad/elpris).

> The integration is under active development and has not yet had a stable release.

## Features

- Stores schedules with up to eight charging periods in Home Assistant, independently of the Android phone.
- Starts and stops charging at the calculated times.
- Optionally applies a charging-current limit before starting.
- Restores future and active schedules after a Home Assistant restart.
- Provides start, stop and cancel buttons plus schedule-status entities.
- Generates a private, narrowly scoped webhook instead of requiring a Home Assistant access token in the app.
- Guided OCPP setup that first selects a charger and then shows only its compatible controls.
- Generic mode for other chargers that expose a Home Assistant switch and optional number entity.

## Installation

The HACS installation flow will become available with the first release. During development, copy `custom_components/elpris_charging` into the `custom_components` directory of your Home Assistant configuration and restart Home Assistant.

Then open **Settings → Devices & services → Add integration**, search for **Elpris charging control**, and follow the setup flow. The *App connection* sensor contains the Home Assistant URL, private webhook ID and a pairing URI for the Android app.

## Dashboard

[`examples/dashboard.yaml`](examples/dashboard.yaml) is a ready-made dashboard section using only built-in Home Assistant cards. It shows charger state, power, the active Elpris schedule, manual controls, daily energy for the current month and monthly energy for the last year.

Paste the example into a manual dashboard card and replace the example OCPP entity IDs with those of your charger. The energy graph needs a cumulative energy sensor with `device_class: energy` and `state_class: total_increasing`; Home Assistant then calculates consumption from its long-term statistics. The integration does not modify dashboards automatically.

## Security

The webhook accepts only versioned Elpris commands for status, scheduling, cancellation, start and stop. The status response contains only this integration's charger-control and schedule state. Timestamps and charging current are validated before the selected Home Assistant entities are called. The Android app does not store a Home Assistant username, password or general access token.

The webhook ID is a secret. Do not publish the complete webhook URL or the attributes of the *App connection* sensor. Reinstalling the integration generates a new webhook ID.

## Current scope

The first version controls standard Home Assistant switch and number entities. Native OCPP Smart Charging profiles are planned after the generic scheduling path has been verified with real chargers.

## License

[MIT](LICENSE)
