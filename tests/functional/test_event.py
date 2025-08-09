import asyncio
import logging

import pytest
from appdaemon.appdaemon import AppDaemon

logger = logging.getLogger("AppDaemon._test")

@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize("mode", ["basic", "listen_kwargs"])
async def test_event_callback(ad: AppDaemon, caplog: pytest.LogCaptureFixture, mode: str) -> None:
    app_name = "event_test_app"
    msg = "Hello from EventTestApp"

    with caplog.at_level(logging.DEBUG, logger=f"AppDaemon.{app_name}"):
        async with ad.app_management.app_run_context(app_name, mode=mode, message=msg):
            await asyncio.sleep(0.25)

    assert "EventTestApp initialized" in caplog.text
    assert msg in caplog.text

    match mode:
        case "listen_kwargs":
            assert "'listen_kwargs': 123" in caplog.text

    assert "Event callback executed successfully" in caplog.text
