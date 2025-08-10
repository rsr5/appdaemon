from enum import Enum, auto
from functools import partial

from appdaemon.adapi import ADAPI


class StateTestAppMode(str, Enum):
    """Enum for different modes of the StateTestApp."""

    def _generate_next_value_(name, start, count, last_values):
        return name.upper()

    BASIC = auto()
    LISTEN_KWARGS = auto()
    NEW_STATE_FILTER_POSITIVE = auto()
    NEW_STATE_FILTER_NEGATIVE = auto()
    ATTRIBUTES = auto()
    NEW_ATTRIBUTE_FILTER_POSITIVE = auto()
    NEW_ATTRIBUTE_FILTER_NEGATIVE = auto()



TEST_ENTITY = "test.some_entity"


class StateTestApp(ADAPI):
    """A simple AppDaemon app to test state management."""

    def initialize(self):
        self.log("Hello from AppDaemon")
        self.add_namespace("test", persist=False)
        self.set_namespace("test")

        self.add_entity(TEST_ENTITY, state="initialized")

        listen = partial(self.listen_state, self.state_callback, TEST_ENTITY)
        run_soon = partial(self.run_in, self.change_state, delay=self.delay)

        self.log(f"Running in {self.mode} mode")
        match self.mode:
            case StateTestAppMode.ATTRIBUTES:
                run_soon = partial(run_soon, test_kwarg=self.args["test_kwarg"])
            case StateTestAppMode.LISTEN_KWARGS:
                listen = partial(listen, listen_kwarg=self.args["test_kwarg"])
            case StateTestAppMode.NEW_STATE_FILTER_POSITIVE | StateTestAppMode.NEW_STATE_FILTER_NEGATIVE:
                listen = partial(listen, new=self.args["new"])
            case StateTestAppMode.NEW_ATTRIBUTE_FILTER_POSITIVE | StateTestAppMode.NEW_ATTRIBUTE_FILTER_NEGATIVE:
                listen = partial(listen, attribute=self.args["attribute"], new="changed")
                attrs = {self.args["attribute"]: self.args["value"]}
                run_soon = partial(run_soon, **attrs)

        self.log(f"Calling listen_state with kwargs: {listen.keywords}")
        listen()

        change_state_kwargs = run_soon.keywords.copy()
        change_state_kwargs.pop("delay", None)
        self.log(f"Calling {run_soon.args[0].__name__} with kwargs: {change_state_kwargs}")
        run_soon()

    @property
    def delay(self) -> float:
        return self.args.get("delay", 0.1)

    @property
    def mode(self) -> StateTestAppMode:
        return StateTestAppMode(self.args.get("mode", StateTestAppMode.BASIC))

    def change_state(self, **kwargs) -> None:
        """Change the state of the test_state entity."""
        kwargs.pop("__thread_id", None)
        match self.mode:
            case StateTestAppMode.BASIC:
                self.set_state(TEST_ENTITY, state="changed")
            case StateTestAppMode.NEW_ATTRIBUTE_FILTER_POSITIVE | StateTestAppMode.NEW_ATTRIBUTE_FILTER_NEGATIVE:
                self.set_state(TEST_ENTITY, attributes=kwargs)
            case _:
                self.set_state(TEST_ENTITY, state="changed", attributes=kwargs)

    def state_callback(self, entity: str, attribute: str, old: str, new: str, **kwargs) -> None:
        self.log(f' {entity}.{attribute} '.center(40, '-'))
        self.log(f"{entity}.{attribute} changed from {old} to {new} with kwargs: {kwargs}")

        new_state = self.get_state(entity, attribute="all")
        assert isinstance(new_state, dict), "State should be a dictionary"

        self.log(f"New state for {entity}: {new_state}")
        self.log("State callback executed successfully")
