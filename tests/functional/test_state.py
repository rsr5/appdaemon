
import asyncio
import logging

import pytest
from appdaemon.appdaemon import AppDaemon

logger = logging.getLogger("AppDaemon._test")

@pytest.fixture
def ad_with_state_test_directory(ad: AppDaemon) -> AppDaemon:
    ad.app_dir = ad.config_dir / "apps"
    assert ad.app_dir.exists(), "App directory does not exist"
    return ad


@pytest.mark.functional
@pytest.mark.asyncio(loop_scope="session")
async def test_state_callback(ad_with_state_test_directory: AppDaemon, caplog: pytest.LogCaptureFixture) -> None:
    ad = ad_with_state_test_directory
    logger.info("Test started")
    with caplog.at_level(logging.DEBUG, logger="AppDaemon.state_test_app"):
        async with ad.app_management.app_run_context("state_test_app"):
            await asyncio.sleep(1)  # Allow time for the app to initialize and run
    logger.info("Test completed")

    assert "Hello from AppDaemon" in caplog.text
    assert "State callback executed successfully" in caplog.text


@pytest.mark.functional
@pytest.mark.asyncio(loop_scope="session")
async def test_state_callback_with_kwargs(ad_with_state_test_directory: AppDaemon, caplog: pytest.LogCaptureFixture) -> None:
    ad = ad_with_state_test_directory
    logger.info("Test started")
    with caplog.at_level(logging.DEBUG, logger="AppDaemon.state_test_app"):
        async with ad.app_management.app_run_context("state_test_app", mode='kwargs', delay=0.3):
            await asyncio.sleep(0.5)  # Allow time for the app to initialize and run
    logger.info("Test completed")

    assert "Hello from AppDaemon" in caplog.text
    assert "'attributes': {'my_kwarg': 123" in caplog.text
    assert "State callback executed successfully" in caplog.text
