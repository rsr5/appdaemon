"""This module contains the conftest.py file for functional tests."""


import asyncio
import logging
from collections.abc import AsyncGenerator

import pytest_asyncio
from appdaemon import AppDaemon
from appdaemon.dependency_manager import DependencyManager
from appdaemon.logging import Logging
from appdaemon.models.config import AppConfig
from appdaemon.models.config.appdaemon import AppDaemonConfig
from appdaemon.utils import recursive_get_files

logger = logging.getLogger("AppDaemon._test")


@pytest_asyncio.fixture(scope="function", loop_scope="session")
async def ad(running_loop: asyncio.BaseEventLoop, ad_cfg: AppDaemonConfig) -> AsyncGenerator[AppDaemon]:
    """Pytest fixture that provides a full AppDaemon instance for tests.

    General steps:
      - Create the top-level AppDaemon object.
      - Set the log levels of the main logs to DEBUG.
      - Process the import parths.
      - Set up the dependency manager with the app directory.
      - Disables apps.
    """
    # logger.info(f"Passed loop: {hex(id(running_loop))}")
    assert running_loop == asyncio.get_running_loop(), "The running loop should match the one passed in"

    ad = AppDaemon(
        logging=Logging({"main_log": {"format": "{levelname} {appname}: {message}"}}),
        loop=running_loop,
        ad_config_model=ad_cfg,
    )
    logger.info(f"Created AppDaemon object {hex(id(ad))}")

    for cfg in ad.logging.config.values():
        logger_ = logging.getLogger(cfg["name"])
        logger_.propagate = True
        logger_.setLevel("DEBUG")

    await ad.app_management._process_import_paths()
    config_files = list(recursive_get_files(base=ad.app_dir, suffix=ad.config.ext))
    ad.app_management.dependency_manager = DependencyManager(python_files=list(), config_files=config_files)

    for cfg in ad.app_management.app_config.root.values():
        match cfg:
            case AppConfig() as app_config:
                app_config.disable = True

    ad.start()
    logger.info(f"AppDaemon started with id {hex(id(ad))}")
    yield ad
    logger.info("Back to fixture scope, stopping AppDaemon")
    await ad.stop()
    # TODO: This shouldn't be necessary, but it seems to be needed
    ad.threading.pin_threads = 0

    for cfg in ad.app_management.app_config.root.values():
        match cfg:
            case AppConfig() as app_config:
                app_config.disable = True
