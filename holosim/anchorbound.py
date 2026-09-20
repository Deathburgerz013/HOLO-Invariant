"""ANCHORBOUND: a tiny deterministic Game Boy-style loop puzzle.

Run with ``python -m holosim.anchorbound`` after installing the optional game
dependency: ``python -m pip install -e .[game]``.

The simulation is stdlib-only and driven through ``step(state, action)`` so
tests and future agents use the same eight-button interface as human players.
Pygame is imported only by ``run()`` and rendering helpers.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Any


WIDTH = 20
HEIGHT = 14
TICK_RATE = 30
LOOP_TICKS = 30 * TICK_RATE
PLAYER_START = (10, 12)
BASE_BLOCK = (6, 8)
BASE_KEY = (10, 4)
SENTINEL_ROUTE = ((7, 6), (8, 6), (9, 6), (10, 6), (11, 6), (12, 6), (13, 6))
DOOR = (10, 0)
CRACKED_WALL = (17, 7)
SECRET_EXIT = (18, 7)
PRESSURE_PLATE = (8, 8)

PALETTE = ("#081820", "#346856", "#88c070", "#e0f8d0")
COLOR_OVERLAY = {
    "player": "#ffe66d",
    "sentinel": "#ff6b6b",
    "key": "#ffd166",
    "block": "#c98b5b",
    "door": "#70d6ff",
    "rift": "#d66efd",
    "plate": "#7bf1a8",
}

ROOM = (
    "##########D#########",
    "#..................#",
    "#..#####....#####..#",
    "#..#............#..#",
    "#..#......K.....#..#",
    "#..#............#..#",
    "#..................#",
    "#..#####......##.CX#",
    "#.....B............#",
    "#..#####......####.#",
    "#..................#",
    "#..######..######..#",
    "#.........P........#",
    "####################",
)


class Action(str, Enum):
    NONE = "NONE"
    UP = "UP"
    DOWN = "DOWN"
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    A = "A"
    B = "B"
    START = "START"
    SELECT = "SELECT"


class Phase(str, Enum):
    TITLE = "TITLE"
    PLAYING = "PLAYING"
    ANCHOR = "ANCHOR"
    PAUSED = "PAUSED"
    VICTORY = "VICTORY"


class Fact(str, Enum):
    SENTINEL_DEFEATED = "SENTINEL DEFEATED"
    BLOCK_REMAINS_MOVED = "BLOCK REMAINS MOVED"
    KEY_RETAINED = "KEY RETAINED"


DIRECTIONS = {
    Action.UP: (0, -1),
    Action.DOWN: (0, 1),
    Action.LEFT: (-1, 0),
    Action.RIGHT: (1, 0),
}


@dataclass(frozen=True)
class GameState:
    phase: Phase
    tick: int
    loop_index: int
    ticks_remaining: int
    player: tuple[int, int]
    facing: Action
    sentinel_index: int
    sentinel_direction: int
    sentinel_alive: bool
    block: tuple[int, int]
    key_present: bool
    key_held: bool
    discovered: tuple[Fact, ...]
    active_anchor: Fact | None
    anchor_options: tuple[Fact | None, ...]
    anchor_index: int
    candidate_block: tuple[int, int]
    rift_active: bool
    rift_open: bool
    contradiction_warning: int
    total_ticks: int
    corrections: int
    secret_found: bool
    message: str
    message_ticks: int
    move_cooldown: int


def initial_state(*, playing: bool = False) -> GameState:
    """Return a deterministic new game state."""
    return GameState(
        phase=Phase.PLAYING if playing else Phase.TITLE,
        tick=0,
        loop_index=1,
        ticks_remaining=LOOP_TICKS,
        player=PLAYER_START,
        facing=Action.UP,
        sentinel_index=0,
        sentinel_direction=1,
        sentinel_alive=True,
        block=BASE_BLOCK,
        key_present=True,
        key_held=False,
        discovered=(),
        active_anchor=None,
        anchor_options=(None,),
        anchor_index=0,
        candidate_block=BASE_BLOCK,
        rift_active=False,
        rift_open=False,
        contradiction_warning=0,
        total_ticks=0,
        corrections=0,
        secret_found=False,
        message="FIND WHAT SURVIVES",
        message_ticks=90,
        move_cooldown=0,
    )


def _add_fact(state: GameState, fact: Fact) -> tuple[Fact, ...]:
    return state.discovered if fact in state.discovered else (*state.discovered, fact)


def _tile(position: tuple[int, int]) -> str:
    x, y = position
    if not 0 <= x < WIDTH or not 0 <= y < HEIGHT:
        return "#"
    if position == DOOR:
        return "D"
    if position == CRACKED_WALL:
        return "C"
    if position == SECRET_EXIT:
        return "X"
    character = ROOM[y][x]
    return "." if character in "PKB" else character


def _sentinel_position(state: GameState) -> tuple[int, int]:
    return SENTINEL_ROUTE[state.sentinel_index]


def _blocked(state: GameState, position: tuple[int, int]) -> bool:
    tile = _tile(position)
    if tile == "#" or (
        tile == "D" and not (state.key_held or state.block == PRESSURE_PLATE)
    ):
        return True
    if tile == "C" and not (state.rift_active and state.rift_open):
        return True
    if position == state.block:
        return True
    if state.sentinel_alive and position == _sentinel_position(state):
        return True
    return False


def _adjacent(position: tuple[int, int], facing: Action) -> tuple[int, int]:
    dx, dy = DIRECTIONS.get(facing, (0, 0))
    return position[0] + dx, position[1] + dy


def _start_loop(state: GameState, anchor: Fact | None) -> GameState:
    sentinel_alive = anchor is not Fact.SENTINEL_DEFEATED
    block = state.candidate_block if anchor is Fact.BLOCK_REMAINS_MOVED else BASE_BLOCK
    key_held = anchor is Fact.KEY_RETAINED
    rift_active = key_held  # the base room also respawns its key: a visible contradiction
    return replace(
        state,
        phase=Phase.PLAYING,
        tick=0,
        loop_index=state.loop_index + 1,
        ticks_remaining=LOOP_TICKS,
        player=PLAYER_START,
        facing=Action.UP,
        sentinel_index=0,
        sentinel_direction=1,
        sentinel_alive=sentinel_alive,
        block=block,
        key_present=True,
        key_held=key_held,
        active_anchor=anchor,
        anchor_options=(None,),
        anchor_index=0,
        rift_active=rift_active,
        rift_open=False,
        contradiction_warning=150 if rift_active else 0,
        message="THE WORLD DISAGREES" if rift_active else "ANCHOR APPLIED",
        message_ticks=75,
        move_cooldown=0,
    )


def _open_anchor_menu(state: GameState) -> GameState:
    options: tuple[Fact | None, ...] = (None, *state.discovered)
    return replace(
        state,
        phase=Phase.ANCHOR,
        anchor_options=options,
        anchor_index=0,
        candidate_block=state.block,
        message="CHOOSE ONE FACT",
        message_ticks=0,
    )


def _move_sentinel(state: GameState) -> GameState:
    if not state.sentinel_alive or state.tick % 12:
        return state
    next_index = state.sentinel_index + state.sentinel_direction
    direction = state.sentinel_direction
    if not 0 <= next_index < len(SENTINEL_ROUTE):
        direction *= -1
        next_index = state.sentinel_index + direction
    if SENTINEL_ROUTE[next_index] == state.block:
        direction *= -1
        next_index = state.sentinel_index + direction
        if not 0 <= next_index < len(SENTINEL_ROUTE) or SENTINEL_ROUTE[next_index] == state.block:
            return replace(state, sentinel_direction=direction)
    state = replace(state, sentinel_index=next_index, sentinel_direction=direction)
    if _sentinel_position(state) == state.player:
        return replace(
            state,
            player=PLAYER_START,
            ticks_remaining=max(1, state.ticks_remaining - 90),
            corrections=state.corrections + 1,
            message="DRIFT CORRECTED YOU",
            message_ticks=45,
        )
    return state


def _interact(state: GameState) -> GameState:
    target = _adjacent(state.player, state.facing)
    if state.sentinel_alive and target == _sentinel_position(state):
        return replace(
            state,
            sentinel_alive=False,
            discovered=_add_fact(state, Fact.SENTINEL_DEFEATED),
            message="FACT FOUND: SENTINEL DEFEATED",
            message_ticks=60,
        )
    if state.key_present and target == BASE_KEY:
        return replace(
            state,
            key_present=False,
            key_held=True,
            discovered=_add_fact(state, Fact.KEY_RETAINED),
            message="FACT FOUND: KEY RETAINED",
            message_ticks=60,
        )
    if target == DOOR and (state.key_held or state.block == PRESSURE_PLATE):
        return replace(state, phase=Phase.VICTORY, message="ANCHOR HOLDS", message_ticks=0)
    return replace(state, message="NOTHING ANSWERS", message_ticks=20)


def _push(state: GameState) -> GameState:
    target = _adjacent(state.player, state.facing)
    if target != state.block:
        return state
    beyond = _adjacent(target, state.facing)
    if _tile(beyond) in "#DCX" or (
        state.sentinel_alive and beyond == _sentinel_position(state)
    ):
        return replace(state, message="BLOCKED", message_ticks=20)
    return replace(
        state,
        player=target,
        block=beyond,
        candidate_block=beyond,
        discovered=_add_fact(state, Fact.BLOCK_REMAINS_MOVED),
        message="FACT FOUND: BLOCK MOVED",
        message_ticks=60,
    )


def step(state: GameState, action: Action | str) -> GameState:
    """Advance one deterministic simulation tick using one Game Boy-style action."""
    try:
        action = Action(action)
    except (ValueError, TypeError) as exc:
        raise ValueError("unknown ANCHORBOUND action") from exc

    if state.phase is Phase.TITLE:
        return initial_state(playing=True) if action in {Action.START, Action.A} else state
    if state.phase is Phase.VICTORY:
        return initial_state(playing=True) if action in {Action.START, Action.A} else state
    if state.phase is Phase.PAUSED:
        return replace(state, phase=Phase.PLAYING) if action is Action.START else state
    if state.phase is Phase.ANCHOR:
        if action is Action.UP:
            return replace(state, anchor_index=(state.anchor_index - 1) % len(state.anchor_options))
        if action is Action.DOWN:
            return replace(state, anchor_index=(state.anchor_index + 1) % len(state.anchor_options))
        if action is Action.B:
            return replace(state, phase=Phase.PLAYING)
        if action is Action.A:
            return _start_loop(state, state.anchor_options[state.anchor_index])
        return state

    ticks = state.ticks_remaining - 1
    state = replace(
        state,
        tick=state.tick + 1,
        total_ticks=state.total_ticks + 1,
        ticks_remaining=ticks,
        message_ticks=max(0, state.message_ticks - 1),
        contradiction_warning=max(0, state.contradiction_warning - 1),
        move_cooldown=max(0, state.move_cooldown - 1),
    )
    if state.rift_active:
        state = replace(state, rift_open=(state.tick // 20) % 2 == 1)
    state = _move_sentinel(state)
    if state.ticks_remaining <= 0 or action is Action.SELECT:
        return _open_anchor_menu(state)
    if action is Action.START:
        return replace(state, phase=Phase.PAUSED)
    if action in DIRECTIONS:
        if state.move_cooldown:
            return state
        target = _adjacent(state.player, action)
        state = replace(state, facing=action)
        if not _blocked(state, target):
            if target == DOOR and (state.key_held or state.block == PRESSURE_PLATE):
                return replace(
                    state,
                    player=target,
                    phase=Phase.VICTORY,
                    message="ANCHOR HOLDS",
                    message_ticks=0,
                )
            if target == SECRET_EXIT and state.rift_active and state.rift_open:
                return replace(
                    state,
                    player=target,
                    phase=Phase.VICTORY,
                    secret_found=True,
                    message="YOU BROKE THE RULE CORRECTLY",
                    message_ticks=0,
                )
            state = replace(state, player=target, move_cooldown=2)
            if target == BASE_KEY and state.key_present:
                state = replace(
                    state,
                    key_present=False,
                    key_held=True,
                    discovered=_add_fact(state, Fact.KEY_RETAINED),
                    message="KEY GET! IT CAN SURVIVE",
                    message_ticks=60,
                )
    elif action is Action.A:
        state = _interact(state)
    elif action is Action.B:
        state = _push(state)
    return state


def state_snapshot(state: GameState) -> dict[str, Any]:
    """Return a JSON-safe observation for tests and future nonhuman players."""
    return {
        "phase": state.phase.value,
        "tick": state.tick,
        "loop_index": state.loop_index,
        "ticks_remaining": state.ticks_remaining,
        "player": list(state.player),
        "facing": state.facing.value,
        "sentinel": list(_sentinel_position(state)) if state.sentinel_alive else None,
        "block": list(state.block),
        "key_present": state.key_present,
        "key_held": state.key_held,
        "discovered": [fact.value for fact in state.discovered],
        "active_anchor": state.active_anchor.value if state.active_anchor else None,
        "rift_active": state.rift_active,
        "rift_open": state.rift_open,
        "corrections": state.corrections,
        "secret_found": state.secret_found,
        "move_cooldown": state.move_cooldown,
    }


def validate_room() -> None:
    """Fail if the embedded vertical-slice room is structurally unusable."""
    if len(ROOM) != HEIGHT or any(len(row) != WIDTH for row in ROOM):
        raise ValueError("ANCHORBOUND room must be exactly 20 by 14 tiles")
    if any(ROOM[0][x] != "#" for x in range(WIDTH) if x != DOOR[0]):
        raise ValueError("ANCHORBOUND north border is open outside the door")
    if any(ROOM[HEIGHT - 1][x] != "#" for x in range(WIDTH)):
        raise ValueError("ANCHORBOUND south border is open")
    if any(ROOM[y][0] != "#" or ROOM[y][WIDTH - 1] != "#" for y in range(HEIGHT)):
        raise ValueError("ANCHORBOUND side border is open")
    if ROOM[PLAYER_START[1]][PLAYER_START[0]] != "P":
        raise ValueError("ANCHORBOUND player start marker is missing")
    if ROOM[BASE_KEY[1]][BASE_KEY[0]] != "K":
        raise ValueError("ANCHORBOUND key marker is missing")
    if ROOM[BASE_BLOCK[1]][BASE_BLOCK[0]] != "B":
        raise ValueError("ANCHORBOUND block marker is missing")
    if ROOM[CRACKED_WALL[1]][CRACKED_WALL[0]] != "C":
        raise ValueError("ANCHORBOUND cracked wall marker is missing")
    if ROOM[SECRET_EXIT[1]][SECRET_EXIT[0]] != "X":
        raise ValueError("ANCHORBOUND secret exit marker is missing")


validate_room()


def _draw_text(pygame: Any, surface: Any, font: Any, text: str, position: tuple[int, int], color: str) -> None:
    image = font.render(text, False, color)
    surface.blit(image, position)


def _context_prompt(state: GameState) -> str:
    target = _adjacent(state.player, state.facing)
    if state.sentinel_alive and target == _sentinel_position(state):
        return "Z TAG SENTINEL"
    if target == state.block:
        return "X PUSH BLOCK"
    if target == DOOR:
        return "DOOR NEEDS KEY OR PLATE"
    if state.rift_active:
        return "RIFT OPENS CRACKED WALL"
    return "ARROWS MOVE  Z USE"


def _render(
    pygame: Any,
    surface: Any,
    font: Any,
    state: GameState,
    *,
    color_overlay: bool = True,
) -> None:
    dark, mid, light, bright = PALETTE
    surface.fill(dark)
    if state.phase is Phase.TITLE:
        _draw_text(pygame, surface, font, "ANCHORBOUND", (43, 45), bright)
        _draw_text(pygame, surface, font, "THE WORLD RESETS", (31, 65), light)
        _draw_text(pygame, surface, font, "ARROWS MOVE", (47, 84), light)
        _draw_text(pygame, surface, font, "Z USE  X PUSH", (42, 96), light)
        _draw_text(pygame, surface, font, "PRESS START", (47, 116), bright)
        return
    if state.phase is Phase.VICTORY:
        title = "SECRET ANCHORED" if state.secret_found else "ANCHOR HOLDS"
        _draw_text(pygame, surface, font, title, (35, 38), bright)
        _draw_text(pygame, surface, font, f"LOOPS {state.loop_index}", (50, 62), light)
        _draw_text(pygame, surface, font, f"TIME {state.total_ticks // TICK_RATE}s", (50, 74), light)
        _draw_text(pygame, surface, font, f"FIXES {state.corrections}", (50, 86), light)
        _draw_text(pygame, surface, font, "PRESS START", (47, 110), bright)
        return
    if state.phase is Phase.ANCHOR:
        _draw_text(pygame, surface, font, "WHAT SURVIVES?", (38, 25), bright)
        for index, option in enumerate(state.anchor_options):
            label = "NOTHING" if option is None else option.value
            prefix = ">" if index == state.anchor_index else " "
            _draw_text(pygame, surface, font, prefix + label[:22], (18, 48 + 14 * index), bright if prefix == ">" else light)
        _draw_text(pygame, surface, font, "A HOLD   B RETURN", (28, 124), mid)
        return

    pygame.draw.rect(surface, mid, (0, 0, 160, 16))
    seconds = max(0, (state.ticks_remaining + TICK_RATE - 1) // TICK_RATE)
    _draw_text(pygame, surface, font, f"T {seconds:02d}", (3, 4), bright)
    anchor = "NONE" if state.active_anchor is None else state.active_anchor.value.split()[0]
    _draw_text(pygame, surface, font, f"ANCHOR {anchor}", (55, 4), bright)
    for y, row in enumerate(ROOM):
        for x, tile in enumerate(row):
            rect = (x * 8, 16 + y * 8, 8, 8)
            if tile == "#":
                pygame.draw.rect(surface, mid, rect)
                pygame.draw.rect(surface, light, (rect[0] + 1, rect[1] + 1, 6, 2))
            else:
                pygame.draw.rect(surface, dark, rect)
                if (x + y) % 2 == 0:
                    surface.set_at((rect[0] + 2, rect[1] + 2), mid)
    # door, cracked wall, secret exit
    entity = COLOR_OVERLAY if color_overlay else {key: bright for key in COLOR_OVERLAY}
    pygame.draw.rect(surface, entity["door"], (DOOR[0] * 8, 16, 8, 8))
    pygame.draw.rect(surface, mid if not state.rift_open else entity["rift"], (CRACKED_WALL[0] * 8, 16 + CRACKED_WALL[1] * 8, 8, 8))
    pygame.draw.rect(surface, entity["rift"] if state.rift_active else mid, (SECRET_EXIT[0] * 8, 16 + SECRET_EXIT[1] * 8, 8, 8), 1)
    # block and key
    bx, by = state.block
    pygame.draw.rect(
        surface,
        entity["plate"] if state.block == PRESSURE_PLATE else mid,
        (PRESSURE_PLATE[0] * 8 + 2, 16 + PRESSURE_PLATE[1] * 8 + 2, 4, 4),
        1,
    )
    pygame.draw.rect(surface, entity["block"], (bx * 8 + 1, 16 + by * 8 + 1, 6, 6))
    pygame.draw.rect(surface, mid, (bx * 8 + 3, 16 + by * 8 + 3, 2, 2))
    if state.key_present:
        kx, ky = BASE_KEY
        pygame.draw.circle(surface, entity["key"], (kx * 8 + 3, 16 + ky * 8 + 3), 2)
        pygame.draw.line(surface, entity["key"], (kx * 8 + 4, 16 + ky * 8 + 4), (kx * 8 + 7, 16 + ky * 8 + 7), 1)
    if state.sentinel_alive:
        sx, sy = _sentinel_position(state)
        pygame.draw.rect(surface, entity["sentinel"], (sx * 8 + 1, 16 + sy * 8 + 1, 6, 6))
        surface.set_at((sx * 8 + 2, 16 + sy * 8 + 3), dark)
        surface.set_at((sx * 8 + 5, 16 + sy * 8 + 3), dark)
    if state.rift_active:
        rx = 17 * 8 + (state.tick % 3) - 1
        ry = 16 + 6 * 8
        pygame.draw.line(surface, entity["rift"], (rx, ry), (rx + 5, ry + 15), 2)
        pygame.draw.line(surface, light, (rx + 6, ry), (rx + 1, ry + 15), 1)
    px, py = state.player
    pygame.draw.rect(surface, entity["player"], (px * 8 + 2, 16 + py * 8 + 1, 4, 6))
    pygame.draw.rect(surface, light, (px * 8 + 1, 16 + py * 8 + 3, 6, 3))
    pygame.draw.rect(surface, mid, (0, 128, 160, 16))
    message = "PAUSED" if state.phase is Phase.PAUSED else (state.message if state.message_ticks else _context_prompt(state))
    _draw_text(pygame, surface, font, message[:26], (3, 132), bright)


def _tone(pygame: Any, start_hz: float, end_hz: float, duration: float) -> Any:
    """Generate a tiny mono square-wave cue without external assets."""
    from array import array

    sample_rate = 22_050
    count = int(sample_rate * duration)
    samples = array("h")
    phase = 0.0
    for index in range(count):
        ratio = index / max(1, count - 1)
        frequency = start_hz + (end_hz - start_hz) * ratio
        phase = (phase + frequency / sample_rate) % 1.0
        envelope = 1.0 - ratio
        samples.append(int((3_500 if phase < 0.5 else -3_500) * envelope))
    return pygame.mixer.Sound(buffer=samples.tobytes())


def _build_sounds(pygame: Any) -> dict[str, Any]:
    try:
        if pygame.mixer.get_init() is None:
            pygame.mixer.init(frequency=22_050, size=-16, channels=1)
        return {
            "fact": _tone(pygame, 180, 520, 0.10),
            "reset": _tone(pygame, 520, 90, 0.22),
            "rift": _tone(pygame, 110, 880, 0.18),
            "win": _tone(pygame, 260, 780, 0.28),
        }
    except pygame.error:
        return {}


def run() -> None:
    """Launch the pygame window."""
    try:
        import pygame
    except ImportError as exc:
        raise SystemExit(
            "ANCHORBOUND needs pygame. Install it with: "
            "python -m pip install -e .[game]"
        ) from exc
    pygame.mixer.pre_init(frequency=22_050, size=-16, channels=1)
    pygame.init()
    pygame.display.set_caption("ANCHORBOUND")
    window = pygame.display.set_mode((640, 576))
    surface = pygame.Surface((160, 144))
    font = pygame.font.Font(None, 10)
    clock = pygame.time.Clock()
    sounds = _build_sounds(pygame)
    state = initial_state()
    color_overlay = True
    held: list[Action] = []
    key_actions = {
        pygame.K_UP: Action.UP,
        pygame.K_w: Action.UP,
        pygame.K_DOWN: Action.DOWN,
        pygame.K_s: Action.DOWN,
        pygame.K_LEFT: Action.LEFT,
        pygame.K_a: Action.LEFT,
        pygame.K_RIGHT: Action.RIGHT,
        pygame.K_d: Action.RIGHT,
        pygame.K_z: Action.A,
        pygame.K_SPACE: Action.A,
        pygame.K_x: Action.B,
        pygame.K_LSHIFT: Action.B,
        pygame.K_RETURN: Action.START,
        pygame.K_BACKSPACE: Action.SELECT,
    }
    running = True
    while running:
        pressed = Action.NONE
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_c:
                    color_overlay = not color_overlay
                action = key_actions.get(event.key)
                if action is not None:
                    pressed = action
                    if action in DIRECTIONS and action not in held:
                        held.append(action)
            elif event.type == pygame.KEYUP:
                action = key_actions.get(event.key)
                if action in held:
                    held.remove(action)
        held_action = held[-1] if held and state.phase is Phase.PLAYING else Action.NONE
        action = pressed if pressed is not Action.NONE else held_action
        previous = state
        state = step(state, action)
        cue = None
        if state.phase is Phase.VICTORY and previous.phase is not Phase.VICTORY:
            cue = "win"
        elif state.rift_active and not previous.rift_active:
            cue = "rift"
        elif state.phase is Phase.ANCHOR and previous.phase is Phase.PLAYING:
            cue = "reset"
        elif (
            state.message.startswith("FACT FOUND") or state.message.startswith("KEY GET")
        ) and state.message != previous.message:
            cue = "fact"
        if cue in sounds:
            sounds[cue].play()
        _render(pygame, surface, font, state, color_overlay=color_overlay)
        window.blit(pygame.transform.scale(surface, window.get_size()), (0, 0))
        pygame.display.flip()
        clock.tick(TICK_RATE)
    pygame.quit()


if __name__ == "__main__":
    run()