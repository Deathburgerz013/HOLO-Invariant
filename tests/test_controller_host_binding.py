"""Regression tests for host-bound controller observations."""
import inspect
from holosim.controller_permitted_observation import ControllerPermittedObservation
from holosim.permitted_observation_host import PermittedObservationHost

def test_controller_requires_host_owned_observation_boundary():
    parameters = inspect.signature(ControllerPermittedObservation).parameters
    assert "host" in parameters
    assert "permit_registry_path" not in parameters

def test_controller_cannot_override_host_configuration_per_call():
    parameters = inspect.signature(ControllerPermittedObservation.observe).parameters
    forbidden = {"allowed_root", "observed_at", "permit_source_secrets", "seen_occurrence_ids", "permit_registry_path", "clock"}
    assert forbidden.isdisjoint(parameters)

def test_host_remains_the_observation_boundary():
    parameters = inspect.signature(PermittedObservationHost.observe).parameters
    assert "permit_occurrence" in parameters
    assert "expected_content" in parameters
