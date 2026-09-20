from __future__ import annotations

import json
import sys
from dataclasses import replace

import pytest

from holosim.anchorbound import (
    BASE_BLOCK,
    BASE_KEY,
    CRACKED_WALL,
    DOOR,
    HEIGHT,
    LOOP_TICKS,
    PLAYER_START,
    PRESSURE_PLATE,
    ROOM,
    SECRET_EXIT,
    SENTINEL_ROUTE,
    WIDTH,
    Action,
    Fact,
    Phase,
    initial_state,
    state_snapshot,
    step,
    validate_room,
)


def test_room_is_exact_game_boy_grid_with_closed_border() -> None:
    validate_room()
    assert len(ROOM) == HEIGHT == 14
    assert all(len(row) == WIDTH == 20 for row in ROOM)
    assert ROOM[0][DOOR[0]] == "D"
    assert ROOM[CRACKED_WALL[1]][CRACKED_WALL[0]] == "C"
    assert ROOM[SECRET_EXIT[1]][SECRET_EXIT[0]] == "X"


def test_initial_state_is_deterministic_and_title_starts_with_game_buttons() -> None:
    assert initial_state() == initial_state()
    assert step(initial_state(), Action.START).phase is Phase.PLAYING
    assert step(initial_state(), Action.A).phase is Phase.PLAYING
    assert step(initial_state(), Action.NONE).phase is Phase.TITLE


def test_all_eight_buttons_and_none_are_valid_actions() -> None:
    state = initial_state(playing=True)
    for action in Action:
        result = step(state, action)
        assert result.phase in Phase
    with pytest.raises(ValueError, match="unknown"):
        step(state, "CHEAT")


def test_movement_is_four_directional_and_walls_block() -> None:
    state = initial_state(playing=True)
    moved = step(state, Action.LEFT)
    assert moved.player == (PLAYER_START[0] - 1, PLAYER_START[1])
    against_wall = replace(state, player=(1, 1), facing=Action.LEFT)
    assert step(against_wall, Action.LEFT).player == (1, 1)


def test_start_pauses_without_consuming_paused_time() -> None:
    state = step(initial_state(playing=True), Action.START)
    assert state.phase is Phase.PAUSED
    remaining = state.ticks_remaining
    state = step(state, Action.NONE)
    assert state.ticks_remaining == remaining
    assert step(state, Action.START).phase is Phase.PLAYING


def test_select_and_timeout_open_anchor_menu() -> None:
    state = step(initial_state(playing=True), Action.SELECT)
    assert state.phase is Phase.ANCHOR
    timeout = replace(initial_state(playing=True), ticks_remaining=1)
    assert step(timeout, Action.NONE).phase is Phase.ANCHOR


def test_anchor_menu_wraps_and_can_return_without_reset() -> None:
    state = replace(
        initial_state(playing=True),
        discovered=(Fact.SENTINEL_DEFEATED, Fact.KEY_RETAINED),
    )
    state = step(state, Action.SELECT)
    assert len(state.anchor_options) == 3
    assert step(state, Action.UP).anchor_index == 2
    assert step(state, Action.DOWN).anchor_index == 1
    assert step(state, Action.B).phase is Phase.PLAYING


def test_defeating_sentinel_discovers_fact_and_anchor_removes_it_next_loop() -> None:
    sentinel = SENTINEL_ROUTE[0]
    state = replace(
        initial_state(playing=True),
        player=(sentinel[0], sentinel[1] + 1),
        facing=Action.UP,
    )
    state = step(state, Action.A)
    assert state.sentinel_alive is False
    assert Fact.SENTINEL_DEFEATED in state.discovered
    state = step(state, Action.SELECT)
    state = replace(state, anchor_index=state.anchor_options.index(Fact.SENTINEL_DEFEATED))
    state = step(state, Action.A)
    assert state.phase is Phase.PLAYING
    assert state.active_anchor is Fact.SENTINEL_DEFEATED
    assert state.sentinel_alive is False


def test_key_pickup_discovers_fact() -> None:
    state = replace(
        initial_state(playing=True),
        player=(BASE_KEY[0], BASE_KEY[1] + 1),
        facing=Action.UP,
    )
    state = step(state, Action.A)
    assert state.key_held is True
    assert state.key_present is False
    assert Fact.KEY_RETAINED in state.discovered


def test_walking_onto_key_auto_collects_it() -> None:
    state = replace(
        initial_state(playing=True),
        player=(BASE_KEY[0], BASE_KEY[1] + 1),
        facing=Action.UP,
    )
    state = step(state, Action.UP)
    assert state.player == BASE_KEY
    assert state.key_held is True
    assert state.key_present is False
    assert state.message.startswith("KEY GET")


def test_key_opens_main_door() -> None:
    state = replace(
        initial_state(playing=True),
        player=(DOOR[0], 1),
        facing=Action.UP,
        key_held=True,
        key_present=False,
    )
    state = step(state, Action.A)
    assert state.phase is Phase.VICTORY
    assert state.secret_found is False


def test_walking_through_unlocked_door_wins() -> None:
    state = replace(
        initial_state(playing=True),
        player=(DOOR[0], 1),
        facing=Action.UP,
        key_held=True,
        key_present=False,
    )
    state = step(state, Action.UP)
    assert state.phase is Phase.VICTORY
    assert state.player == DOOR


def test_block_push_discovers_fact_and_moves_only_onto_floor() -> None:
    state = replace(
        initial_state(playing=True),
        player=(BASE_BLOCK[0] - 1, BASE_BLOCK[1]),
        facing=Action.RIGHT,
    )
    state = step(state, Action.B)
    assert state.block == (BASE_BLOCK[0] + 1, BASE_BLOCK[1])
    assert state.player == BASE_BLOCK
    assert Fact.BLOCK_REMAINS_MOVED in state.discovered
    blocked = replace(state, block=(1, 1), player=(2, 1), facing=Action.LEFT)
    assert step(blocked, Action.B).block == (1, 1)


def test_player_can_push_block_onto_pressure_plate() -> None:
    state = replace(
        initial_state(playing=True),
        player=(BASE_BLOCK[0] - 1, BASE_BLOCK[1]),
        facing=Action.RIGHT,
    )
    state = step(state, Action.B)
    state = step(state, Action.B)
    assert state.block == PRESSURE_PLATE


def test_block_anchor_preserves_position_and_pressure_plate_opens_door() -> None:
    state = replace(
        initial_state(playing=True),
        block=PRESSURE_PLATE,
        candidate_block=PRESSURE_PLATE,
        discovered=(Fact.BLOCK_REMAINS_MOVED,),
    )
    state = step(state, Action.SELECT)
    state = replace(state, anchor_index=state.anchor_options.index(Fact.BLOCK_REMAINS_MOVED))
    state = step(state, Action.A)
    assert state.block == PRESSURE_PLATE
    state = replace(state, player=(DOOR[0], 1), facing=Action.UP)
    assert step(state, Action.A).phase is Phase.VICTORY


def test_unanchored_block_and_key_reset_to_base_state() -> None:
    state = replace(
        initial_state(playing=True),
        block=PRESSURE_PLATE,
        key_present=False,
        key_held=True,
        discovered=(Fact.BLOCK_REMAINS_MOVED, Fact.KEY_RETAINED),
    )
    state = step(state, Action.SELECT)
    state = step(state, Action.A)  # NOTHING
    assert state.block == BASE_BLOCK
    assert state.key_present is True
    assert state.key_held is False


def test_key_retained_creates_visible_deterministic_contradiction() -> None:
    state = replace(
        initial_state(playing=True),
        key_present=False,
        key_held=True,
        discovered=(Fact.KEY_RETAINED,),
    )
    state = step(state, Action.SELECT)
    state = replace(state, anchor_index=state.anchor_options.index(Fact.KEY_RETAINED))
    state = step(state, Action.A)
    assert state.key_held is True
    assert state.key_present is True
    assert state.rift_active is True
    assert state.contradiction_warning > 0
    assert state.message == "THE WORLD DISAGREES"


def test_rift_toggles_on_fixed_ticks_and_controls_cracked_wall() -> None:
    state = replace(initial_state(playing=True), rift_active=True, tick=18)
    closed = step(state, Action.NONE)
    opened = step(closed, Action.NONE)
    assert closed.rift_open is False
    assert opened.rift_open is True
    traveler = replace(opened, player=(CRACKED_WALL[0] - 1, CRACKED_WALL[1]))
    assert step(traveler, Action.RIGHT).player == CRACKED_WALL


def test_secret_exit_requires_active_open_rift() -> None:
    base = replace(
        initial_state(playing=True),
        tick=19,
        player=(SECRET_EXIT[0] - 1, SECRET_EXIT[1]),
        facing=Action.RIGHT,
    )
    assert step(base, Action.RIGHT).phase is Phase.PLAYING
    secret = replace(base, rift_active=True, rift_open=True)
    won = step(secret, Action.RIGHT)
    assert won.phase is Phase.VICTORY
    assert won.secret_found is True


def test_sentinel_patrol_is_deterministic_and_block_can_stop_route() -> None:
    state = replace(initial_state(playing=True), tick=11)
    moved = step(state, Action.NONE)
    assert moved.sentinel_index == 1
    blocked = replace(state, block=SENTINEL_ROUTE[1])
    stopped = step(blocked, Action.NONE)
    assert stopped.sentinel_index == 0


def test_sentinel_contact_corrects_player_and_costs_time() -> None:
    state = replace(
        initial_state(playing=True),
        tick=11,
        player=SENTINEL_ROUTE[1],
    )
    corrected = step(state, Action.NONE)
    assert corrected.player == PLAYER_START
    assert corrected.corrections == 1
    assert corrected.ticks_remaining < LOOP_TICKS - 1


def test_same_state_and_actions_produce_identical_results() -> None:
    actions = [Action.LEFT, Action.UP, Action.NONE, Action.RIGHT, Action.A] * 20
    first = initial_state(playing=True)
    second = initial_state(playing=True)
    for action in actions:
        first = step(first, action)
        second = step(second, action)
    assert first == second
    assert state_snapshot(first) == state_snapshot(second)


def test_snapshot_is_json_safe_and_does_not_expose_mutable_state() -> None:
    state = initial_state(playing=True)
    snapshot = state_snapshot(state)
    json.dumps(snapshot, allow_nan=False)
    snapshot["player"][0] = 99
    assert state.player == PLAYER_START


def test_headless_simulation_does_not_import_pygame() -> None:
    before = sys.modules.get("pygame")
    state = step(initial_state(playing=True), Action.NONE)
    assert state.phase is Phase.PLAYING
    assert sys.modules.get("pygame") is before