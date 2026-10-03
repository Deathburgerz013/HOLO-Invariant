"""Scripted transport tests; these do not evaluate actual models."""
import base64
import json
from copy import deepcopy

import pytest

from holosim.cross_model_correction_handoff import (
    build_material, load_fixture, prompts, recorded_call, run_experiment, score,
)
from holosim.local_ollama_adapter import LocalOllamaAdapterError, request_local_ollama_json


class Response:
    def __init__(self, raw):
        self.raw = raw
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False
    def read(self, size=-1):
        return self.raw if size < 0 else self.raw[:size]


def correct():
    return {"active_rule_id": "rule-current", "retained_rule_ids": ["rule-original", "rule-current"],
            "supersedes": ["rule-original", "rule-current"], "stale_plan_blocked": True, "answers": [3, 4, 0]}


class Scripted:
    def __init__(self, outputs=None, same_digest=False):
        self.requests = []
        self.outputs = outputs
        self.same_digest = same_digest
    def __call__(self, request, timeout):
        if isinstance(request, str):
            return Response(json.dumps({"models": [{"name": "model-a", "digest": "a" * 64},
                {"name": "model-b", "digest": ("a" if self.same_digest else "b") * 64}]}).encode())
        body = json.loads(request.data)
        self.requests.append(body)
        index = len(self.requests) - 1
        output = self.outputs[index] if self.outputs else ({"handoff_summary": "Use the revised rule; retain original."} if index == 0 else correct())
        return Response(json.dumps({"done": True, "model": body["model"], "response": json.dumps(output),
            "eval_count": 40, "prompt_eval_count": 400, "done_reason": "stop"}).encode())


def test_both_cases_equal_budgets_stateless_raw_retained():
    transport = Scripted()
    result = run_experiment(sender_model="model-a", receiver_model="model-b", opener=transport)
    assert len(transport.requests) == 9 and len(result["trials"]) == 8
    assert {x["case"] for x in result["trials"]} == {"same_model_fresh_request", "cross_model_fresh_request"}
    assert all(x["score"]["all_checks_passed"] for x in result["trials"])
    assert all("context" not in x for x in transport.requests)
    assert all(x["options"] == {"num_gpu": 0, "num_predict": 512, "num_ctx": 8192, "seed": 0, "temperature": 0} for x in transport.requests)
    assert [x["condition"] for x in result["trials"]] == ["notes", "packet", "notes", "packet", "packet", "notes", "packet", "notes"]
    for trial in result["trials"]:
        raw = json.loads(base64.b64decode(trial["call"]["response_bytes_b64"]))
        assert json.loads(raw["response"]) == trial["call"]["output"]
        request = json.loads(base64.b64decode(trial["call"]["request_bytes_b64"]))
        assert request["prompt"] == trial["call"]["prompt"]
    assert result["ranking"] is None and not result["accepted"] and not result["truth_claimed"]
    assert result["write_authority"] == result["execution_authority"] == "NONE"


def test_conditions_preserve_all_same_records():
    fixture = load_fixture()
    material = build_material(fixture)
    sender = {"handoff_summary": "wrong proposed summary"}
    pair = prompts(fixture, material, sender)
    for prompt in pair.values():
        for node in material["topology"]["nodes"]:
            assert node["hash"] in prompt
        assert "wrong proposed summary" in prompt
        assert fixture["original"]["rule"] in prompt and fixture["correction"]["rule"] in prompt
    assert len(material["topology"]["nodes"]) == 3
    assert base64.b64decode(material["chain_bytes_b64"])


@pytest.mark.parametrize("key,value", [("answers", [4, 8, 2]), ("active_rule_id", "rule-original"),
    ("retained_rule_ids", ["rule-current"]), ("supersedes", []), ("stale_plan_blocked", False)])
def test_wrong_output_fails_checks(key, value):
    output = correct(); output[key] = value
    assert not score(output, load_fixture())["all_checks_passed"]


@pytest.mark.parametrize("output", [None, {}, {**correct(), "accepted": True},
    {**correct(), "answers": [True, 4, 0]}, {**correct(), "retained_rule_ids": ["rule-current", "rule-current"]}])
def test_malformed_not_success(output):
    assert not score(output, load_fixture())["schema_valid"]


def test_wrong_sender_preserved_not_upgraded():
    outputs = [{"handoff_summary": "threshold zero"}] + [correct()] * 4
    result = run_experiment(sender_model="model-a", receiver_model="model-b", repeats=1, opener=Scripted(outputs))
    assert "threshold zero" in result["trials"][0]["call"]["prompt"]
    assert result["sender"]["output"] == outputs[0]


def test_producer_bad_schema_aborts():
    result = run_experiment(sender_model="model-a", receiver_model="model-b", opener=Scripted([{}]))
    assert result["status"] == "PRODUCER_FAILED" and result["trials"] == []


def test_identical_declared_weights_refused():
    with pytest.raises(ValueError, match="same declared weights"):
        run_experiment(sender_model="model-a", receiver_model="model-b", opener=Scripted(same_digest=True))


@pytest.mark.parametrize("kwargs", [{"repeats": True}, {"repeats": 0}, {"repeats": 11}, {"timeout": float("nan")},
    {"timeout": 0}, {"num_predict": 0}, {"num_ctx": True}])
def test_invalid_budget_before_model_call(kwargs):
    transport = Scripted()
    with pytest.raises(ValueError):
        run_experiment(sender_model="model-a", receiver_model="model-b", opener=transport, **kwargs)
    assert transport.requests == []


def test_response_error_retained_not_retried():
    def broken(request, timeout):
        return Response(b"not json")
    call = recorded_call("test", model="a", options={"num_predict": 10}, timeout=1, opener=broken)
    assert call["output"] is None and call["error"]
    assert base64.b64decode(call["response_bytes_b64"]) == b"not json"


def test_prompt_bound_before_request():
    with pytest.raises(ValueError, match="prompt exceeds"):
        recorded_call("x" * 49153, model="a", options={}, timeout=1, opener=Scripted())


@pytest.mark.parametrize("options", [{"num_gpu": 1}, {"seed": True}, {"temperature": float("inf")}, {"num_predict": 0}])
def test_adapter_budget_validation(options):
    with pytest.raises(LocalOllamaAdapterError):
        request_local_ollama_json("prompt", generation_options=options, opener=Scripted())


def test_scoring_does_not_mutate():
    output=correct(); before=deepcopy(output)
    assert score(output, load_fixture())["all_checks_passed"]
    assert output == before


def test_all_errors_count_as_attempts():
    transport = Scripted()
    def fail_receivers(request, timeout):
        if not isinstance(request, str) and len(transport.requests) >= 1:
            return Response(b"invalid")
        return transport(request, timeout)
    result = run_experiment(sender_model="model-a", receiver_model="model-b", repeats=1, opener=fail_receivers)
    assert len(result["trials"]) == 4
    assert all(x["call"]["error"] and not x["score"]["all_checks_passed"] for x in result["trials"])
    assert result["summary"]["same_model_fresh_request"]["notes"] == {"attempts": 1, "all_checks_passed": 0, "request_errors": 1}


def test_oversize_response_is_failure():
    def huge(request, timeout):
        return Response(b"x" * 262145)
    call = recorded_call("test", model="a", options={}, timeout=1, opener=huge)
    assert call["output"] is None and "exceeds" in call["error"]


def test_nonfinite_response_is_failure_with_raw_preserved():
    def nonfinite(request, timeout):
        return Response(b'{"done":true,"model":"a","response":"{\\"value\\":NaN}"}')
    call = recorded_call("test", model="a", options={}, timeout=1, opener=nonfinite)
    assert call["output"] is None and call["error"] and call["response_bytes_b64"]


def test_wrong_response_model_is_failure():
    def wrong_model(request, timeout):
        return Response(json.dumps({"done": True, "model": "other", "response": json.dumps(correct())}).encode())
    call = recorded_call("test", model="a", options={}, timeout=1, opener=wrong_model)
    assert call["output"] is None and "response model differs" in call["error"]


def test_cli_preserves_existing_file(tmp_path):
    import subprocess
    import sys
    destination=tmp_path / "already.json"
    destination.write_bytes(b"retained evidence")
    result=subprocess.run([sys.executable, "-m", "holosim.cross_model_correction_handoff", "--sender-model", "a",
        "--receiver-model", "b", "--output", str(destination)], capture_output=True)
    assert result.returncode != 0 and destination.read_bytes() == b"retained evidence"
