
import asyncio
import logging

import pytest
from appdaemon.appdaemon import AppDaemon

logger = logging.getLogger("AppDaemon._test")

@pytest.mark.ci
@pytest.mark.functional
@pytest.mark.parametrize(
    "mode", [
        "BASIC",
        # "ATTRIBUTES",
        "LISTEN_KWARGS",
        "NEW_STATE_FILTER_POSITIVE",
        "NEW_STATE_FILTER_NEGATIVE",
        "NEW_ATTRIBUTE_FILTER_POSITIVE",
        "NEW_ATTRIBUTE_FILTER_NEGATIVE",
    ]
)
@pytest.mark.asyncio(loop_scope="session")
async def test_state_callback(ad: AppDaemon, caplog: pytest.LogCaptureFixture, mode: str) -> None:
    app_args = {"delay": 0.1}
    test_val = 123
    match mode:
        case "ATTRIBUTES" | "LISTEN_KWARGS":
            app_args |= {"test_kwarg": test_val}
        case "NEW_STATE_FILTER_POSITIVE":
            app_args |= {"new": "changed"}
        case "NEW_STATE_FILTER_NEGATIVE":
            app_args |= {"new": "invalid"}

    match mode:
        case "NEW_ATTRIBUTE_FILTER_POSITIVE":
            app_args |= {"attribute": "test_attribute", "value": "changed"}
        case "NEW_ATTRIBUTE_FILTER_NEGATIVE":
            app_args |= {"attribute": "test_attribute", "value": "invalid"}

    with caplog.at_level(logging.DEBUG, logger="AppDaemon.state_test_app"):
        async with ad.app_management.app_run_context("state_test_app", mode=mode, **app_args):
            await asyncio.sleep(0.2)  # Allow time for the app to initialize and run

    assert "Hello from AppDaemon" in caplog.text

    # Assert something that would indicate a successful test
    match mode:
        case "ATTRIBUTES":
            assert f"'attributes': {{'test_kwarg': {test_val}" in caplog.text
        case "LISTEN_KWARGS":
            assert "to changed with kwargs: {'listen_kwarg': 123," in caplog.text
        case "NEW_STATE_FILTER_POSITIVE":
            assert "'state': 'changed'" in caplog.text
        case "NEW_ATTRIBUTE_FILTER_POSITIVE":
            assert "'attributes': {'test_attribute': 'changed'}" in caplog.text

    # Assert whether the state callback was executed
    match mode:
        case "NEW_STATE_FILTER_NEGATIVE" | "NEW_ATTRIBUTE_FILTER_NEGATIVE":
            assert "State callback executed successfully" not in caplog.text
        case _:
            assert "State callback executed successfully" in caplog.text
