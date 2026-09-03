# feat: Add call_ws() method for arbitrary WebSocket messages

## Summary

Adds a `call_ws()` method to the Hass API that allows apps to send arbitrary WebSocket messages to Home Assistant. This provides a generic escape hatch for accessing any [Home Assistant WebSocket API](https://developers.home-assistant.io/docs/api/websocket) command — including those that are not service calls and therefore not reachable via `call_service()`.

## Motivation

Home Assistant exposes many useful WebSocket message types that aren't service calls, such as:
- `frontend/get_user_data` / `frontend/set_user_data` — per-user server-side storage
- `recorder/statistics_during_period` — long-term statistics queries
- `config/area_registry/list` — registry listings

Currently there is no way to reach these from an AppDaemon app without dropping down to the plugin internals. `call_ws()` fills that gap with a single, general-purpose method.

## Usage

```python
# Read per-user data from HA's server-side storage
result = self.call_ws(type="frontend/get_user_data", key="my_app")

# Query long-term statistics
result = self.call_ws(
    type="recorder/statistics_during_period",
    start_time="2026-02-01T00:00:00Z",
    statistic_ids=["sensor.energy_consumption"],
    period="hour",
)
```

## Design decisions

- **Keyword-argument API** (`**message`) — mirrors the existing `websocket_send_json()` internal interface and feels natural in Python.
- **Returns the full response dict** (including `success`, `result`, `error`, `ad_status`, `ad_duration`) — consistent with how `call_service()` returns results.
- **Validates inputs and returns error dicts** rather than raising exceptions — follows the defensive pattern used elsewhere in the Hass API.
- **`id` is managed automatically** by the plugin layer and is rejected if passed by the caller.
- **Supports `namespace`** parameter following the same pattern as `call_service()` and other Hass API methods.
- **Works both sync and async** via the existing `@utils.sync_decorator`.

## Changes

| File | Change |
|------|--------|
| `appdaemon/plugins/hass/hassapi.py` | Add `call_ws()` method to the `Hass` class |
| `docs/HASS_API_REFERENCE.rst` | Add documentation section with examples |
| `tests/unit/test_call_ws.py` | Add 11 unit tests covering validation, success, errors, and namespace resolution |
