![SpotNav logo](assets/spotnav-icon.svg)

# SpotNav charging control for Home Assistant

[![Open your Home Assistant instance and open this repository in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=henrikekblad&repository=spotnav-home-assistant&category=integration)

Home Assistant integration for receiving and executing EV charging schedules from the [SpotNav Android app](https://github.com/henrikekblad/spotnav).

> The integration is under active development. Home Assistant executes the
> schedules and controls the charger through the selected entities.

## Features

- Stores schedules with up to eight charging periods in Home Assistant, independently of the Android phone.
- Starts and stops charging at the calculated times.
- Optionally applies a charging-current limit before starting.
- Restores future and active schedules after a Home Assistant restart.
- Provides start, stop, follow-schedule and cancel buttons plus schedule-status entities.
- Generates a private, narrowly scoped webhook instead of requiring a Home Assistant access token in the app.
- Guided OCPP setup that first selects a charger and then shows only its compatible controls.
- Generic mode for other chargers that expose a Home Assistant switch and optional number entity.

## Installation

1. Open this repository in HACS with the button above and choose **Download**.
2. Restart Home Assistant when HACS asks you to.
3. Open **Settings → Devices & services → Add integration**.
4. Search for **SpotNav charging control**.
5. Choose **OCPP charger** for the guided setup, or **Generic Home Assistant charger** for any charger exposing a control switch.
6. Select the charger and its charge-control switch. Select a current-limit number entity if available.

Existing installations of Elpris charging control can update directly to
SpotNav charging control. The technical integration domain remains unchanged so
the existing configuration, webhook, entities and dashboard or Node-RED
references are preserved. Do not remove the integration before updating.

The integration creates schedule sensors and start, stop, follow-schedule and cancel buttons. **Follow charging schedule** immediately restores the state required by the saved plan: charging inside a configured period and stopped while waiting for the next one. No helper entities or automation blueprint are required.

The scheduled start and end sensors expose the complete non-secret plan as
attributes: `periods`, `amps`, `phases`, `power_kw`, `energy_kwh`, `price_area`,
and `estimated`. These can be used to visualize every charging period in a Home
Assistant or Node-RED dashboard. Pairing secrets remain confined to the separate
*App connection* sensor.

## Connect the Android app

1. Open **Settings → Devices & services → Entities** in Home Assistant.
2. Search for **App connection** on the SpotNav charging-control device.
3. Open the entity and display its attributes. Copy `webhook_id`.
4. In SpotNav, open **Settings → Home Assistant**.
5. Enter the Home Assistant address and paste the private webhook ID. Use HTTPS for internet addresses; a private local IP address or local hostname may use HTTP.
6. Tap **Test connection**.

`webhook_id` is a generated secret for this integration, not a Home Assistant password or long-lived access token. Automatic pairing through the `pairing_uri` attribute is experimental and works with either a configured external HTTPS URL or a private local HTTP address.

In the **EV** tab, **Start now** first applies the amperage currently selected in SpotNav and then enables charging. **Send charging schedule** transfers all calculated periods and the selected amperage. The button indicates whether the calculated schedule is synchronized with Home Assistant or needs updating.

## Dashboard

[`examples/dashboard.yaml`](examples/dashboard.yaml) is a ready-made dashboard section using only built-in Home Assistant cards. It shows charger state, session energy, the active SpotNav schedule, manual controls, daily energy for the current month and monthly energy for the last year.

Paste the example into a manual dashboard card and replace the example OCPP entity IDs with those of your charger. The energy graph needs a cumulative energy sensor with `device_class: energy` and `state_class: total_increasing`; Home Assistant then calculates consumption from its long-term statistics. The integration does not modify dashboards automatically.

## Security

The webhook accepts only versioned SpotNav commands for status, scheduling, cancellation, start and stop. The status response contains only this integration's charger-control and schedule state. Timestamps and charging current are validated before the selected Home Assistant entities are called. The Android app does not store a Home Assistant username, password or general access token.

The webhook ID is a secret. Do not publish the complete webhook URL, screenshots of the ID, or the attributes of the *App connection* sensor. Removing and adding the integration again generates a new webhook ID.

## Troubleshooting

- If OCPP entities are unavailable after a Home Assistant restart, allow the charger time to reconnect.
- Chargers with several connectors may expose connector-specific entities. Select the main charging outlet, commonly connector 1, under the integration's **Configure** action.
- A rejected OCPP remote start or stop can mean there is no active transaction or that the connected vehicle is not requesting energy.
- Internet-facing addresses require HTTPS. Plain HTTP is accepted only for private local addresses and hostnames, and works only while the phone can reach that network.

## Current scope

The current scheduler runs in Home Assistant and controls standard switch and
number entities, including those exposed by OCPP. Native OCPP Smart Charging
profiles stored directly in compatible chargers are planned as an optional mode.

## License

[MIT](LICENSE)
