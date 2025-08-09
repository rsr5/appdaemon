from enum import Enum

from appdaemon.adapi import ADAPI


class SchedulerTestAppMode(str, Enum):
    """Enum for different modes of the SchedulerTestApp."""
    RUN_EVERY = "run_every"


class SchedulerTestApp(ADAPI):
    def initialize(self):
        self.log("SchedulerTestApp initialized")
        self.add_namespace("test", persist=False)
        self.set_namespace("test")

        self.log(f"Running in {self.mode} mode")
        match self.mode:
            case SchedulerTestAppMode.RUN_EVERY:
                start = self.args.get("start", "now")
                interval = self.args["interval"]
                msg = self.args["msg"]
                self.run_every(self.run_every_callback, start=start, interval=interval, msg=msg)

    @property
    def mode(self) -> SchedulerTestAppMode:
        return SchedulerTestAppMode(self.args.get("mode", SchedulerTestAppMode.RUN_EVERY))

    def run_every_callback(self, **kwargs) -> None:
        """Callback function for run_every."""
        self.log(f"Run every callback executed with kwargs: {kwargs}")
