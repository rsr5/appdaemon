from enum import Enum

from appdaemon.adapi import ADAPI


class StateTestAppMode(str, Enum):
    """Enum for different modes of the StateTestApp."""
    BASIC = "basic"
    WITH_KWARGS = "kwargs"


TEST_ENTITY = "test.some_entity"


class StateTestApp(ADAPI):
    """A simple AppDaemon app to test state management."""

    def initialize(self):
        self.log("Hello from AppDaemon")
        self.add_namespace("test", persist=False)
        self.set_namespace("test")

        self.add_entity(TEST_ENTITY, state="initialized")
        self.listen_state(self.state_callback, TEST_ENTITY)

        self.log(f"Running in {self.mode} mode")
        match self.mode:
            case StateTestAppMode.BASIC:
                self.run_in(self.change_state, delay=self.args["delay"])
            case StateTestAppMode.WITH_KWARGS:
                self.run_in(self.change_state, delay=self.args["delay"], my_kwarg=123)

    @property
    def mode(self) -> StateTestAppMode:
        return StateTestAppMode(self.args.get("mode", StateTestAppMode.BASIC))

    def change_state(self, **kwargs) -> None:
        """Change the state of the test_state entity."""
        kwargs.pop("__thread_id", None)
        self.log(f"Changing state of {TEST_ENTITY}")
        self.set_state(TEST_ENTITY, state="changed", attributes=kwargs)
        self.log("Post state change, waiting for callback")

    def state_callback(self, entity: str, attribute: str, old: str, new: str, **kwargs) -> None:
        self.log(f"{entity}.{attribute} changed from {old} to {new} with kwargs: {kwargs}")

        new_state = self.get_state(entity, attribute="all")
        assert isinstance(new_state, dict), "State should be a dictionary"

        self.log(f"New state for {entity}: {new_state}")
        self.log("State callback executed successfully")
