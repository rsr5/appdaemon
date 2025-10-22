from datetime import timedelta
from typing import Any

from appdaemon.adapi import ADAPI, Entity


class BasicNamespaceTester(ADAPI):
    handle: str | None

    def initialize(self) -> None:
        self.set_namespace(self.custom_test_namespace)
        self.logger.info('Current namespaces: %s', sorted(self.current_namespaces))

        self.show_entities()

        exists = self.test_entity.exists()
        self.logger.info(f"Entity exists: {exists}")
        if not exists:
            self.add_entity("sensor.test", state="initial", attributes={"friendly_name": "Test Sensor"})

        self.show_entities()

        non_existence = "sensor.other_entity"
        self.logger.info("Setting %s in default namespace", non_existence)
        self.set_state(non_existence, state="other", attributes={"friendly_name": "Other Entity"})

        self.run_in(self.start_test, self.start_delay)
        self.test_entity.listen_state(self.handle_state)
        self.log(f"Initialized {self.name}")

    @property
    def current_namespaces(self) -> set[str]:
        return set(self.AD.state.state.keys())

    @property
    def custom_test_namespace(self) -> str:
        return self.args.get("custom_namespace", "test_namespace")

    @property
    def start_delay(self) -> timedelta:
        return timedelta(seconds=self.args.get("start_delay", 1.0))

    @property
    def test_entity(self) -> Entity:
        return self.get_entity("sensor.test", check_existence=False)

    def show_entities(self, *args, **kwargs):
        ns = self.AD.state.state.get(self.custom_test_namespace, {})
        entities = sorted(ns.keys())
        self.log('Test entities: %s', entities)
        return entities

    def start_test(self, *args, **kwargs: Any) -> None:
        match kwargs:
            case {"__thread_id": str(thread_id)}:
                self.log(f"Change called from thread {thread_id}")
        self.test_entity.set_state("changed")

    def handle_state(self, entity: str, attribute: str, old: Any, new: Any, **kwargs: Any) -> None:
        self.log(f"State changed for {entity}: {attribute} = {old} -> {new}")
        self.log(f"Test val: {self.args.get('test_val')}")

        full_state = self.test_entity.get_state('all')
        self.log(f"Full state: {full_state}")
