from copy import deepcopy
from datetime import datetime

import pytest
import pytz
from appdaemon.utils import clean_http_kwargs, clean_kwargs

pytestmark = [
    pytest.mark.ci,
    pytest.mark.unit,
]


BASE = {"a": 1, "b": 2.0, "c": "three", "d": True, "e": False, "f": datetime(2025, 9, 22, 12, 0, 0, tzinfo=pytz.utc), "g": None}


def test_clean_kwargs():
    cleaned = dict(clean_kwargs(**BASE))
    assert isinstance(cleaned["f"], str)

    assert cleaned["d"] is True
    assert cleaned["e"] is False
    assert "g" not in cleaned

    kwargs = deepcopy(BASE)

    kwargs["nested"] = deepcopy(BASE)
    kwargs["nested"]["extra"] = deepcopy(BASE)
    cleaned = dict(clean_kwargs(**kwargs))
    assert isinstance(cleaned["nested"]["extra"]["f"], str)


def test_clean_http_kwargs():
    cleaned = dict(clean_http_kwargs(**BASE))
    assert isinstance(cleaned["f"], str)
    assert "e" not in cleaned
    assert "g" not in cleaned
