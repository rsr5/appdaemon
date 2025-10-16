
import logging
import uuid

import pytest

from .utils import AsyncTempTest

logger = logging.getLogger("AppDaemon._test")


@pytest.mark.asyncio(loop_scope="session")
async def test_simple_namespaces(run_app_for_time: AsyncTempTest) -> None:
    """Test simple namespace functionality."""
    test_val = str(uuid.uuid4())
    app_kwargs = {
        "custom_namespace": "test_namespace",
        'start_delay': 0.1,
        "test_val": test_val,
    }
    async with run_app_for_time("basic_namespace_app", 0.5, **app_kwargs) as (ad, caplog):
        assert "Persistent namespace 'test_namespace' initialized from MainThread" in caplog.text

        # In order for this to be in the log, the state change callback must have fired, which means that the entity
        # was created in the correct namespace and the state change was detected.
        assert test_val in caplog.text

        non_existence_warnings = [
            r for r in caplog.records
            if r.levelno >= logging.WARNING and
            r.msg == "Entity %s not found in namespace %s"
        ]
        assert len(non_existence_warnings) == 1, "Only one warning about non-existence should be logged"
