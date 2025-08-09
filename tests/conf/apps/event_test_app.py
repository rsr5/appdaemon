from enum import Enum
from typing import Any

from appdaemon.adapi import ADAPI

TEST_EVENT = "test_event"

class EventTestAppMode(str, Enum):
    """Enum for different modes of the EventTestApp."""
    BASIC = "basic"
    WITH_LISTEN_KWARGS = "listen_kwargs"


class EventTestApp(ADAPI):
    """A simple AppDaemon app to test event handling."""

    def initialize(self):
        self.log("EventTestApp initialized")
        self.add_namespace("test", persist=False)
        self.set_namespace("test")

        self.log(f"Running in {self.mode}")
        match self.mode:
            case EventTestAppMode.BASIC:
                self.listen_event(self.event_callback, event=TEST_EVENT)
            case EventTestAppMode.WITH_LISTEN_KWARGS:
                self.listen_event(self.event_callback, event=TEST_EVENT, listen_kwargs=123)

        self.run_in(self.trigger_event, delay=self.args.get("delay", 0.1), message=self.args.get("message"))
        # self.trigger_event(message=self.args.get("message", "Hello from EventTestApp"))

    @property
    def mode(self) -> EventTestAppMode:
        return EventTestAppMode(self.args.get("mode", EventTestAppMode.BASIC))

    def trigger_event(self, **kwargs: Any) -> None:
        """Trigger a test event."""
        self.log("Triggering test_event")
        self.fire_event(TEST_EVENT, **kwargs)

    def event_callback(self, event_type: str, data: dict[str, Any], **kwargs: Any) -> None:
        """Callback function for handling events."""
        assert isinstance(data, dict), "Event data should be a dictionary"

        self.log(f"Event '{event_type}' received with data: {data}")
        self.log(f"Event kwargs: {kwargs}")
        self.log("Event callback executed successfully")
