#!/usr/bin/env python3
"""A small prototype about isolation, connection, and subjective morality."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Mapping


def sign(value: int) -> int:
    return 1 if value > 0 else -1 if value < 0 else 0


def clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


@dataclass
class Person:
    name: str
    needs: Dict[str, int]
    trust: int = 0
    closeness: int = 0
    alive: bool = True
    memories: List[str] = field(default_factory=list)

    def interpret(self, changes: Mapping[str, int], actor: str) -> int:
        score = sum(self.needs.get(resource, 0) * delta for resource, delta in changes.items())
        if score > 0:
            self.memories.append(f"{actor} helped what mattered to me.")
        elif score < 0:
            self.memories.append(f"{actor} took something I needed.")
        else:
            self.memories.append(f"I could not decide what {actor}'s action meant.")
        self.trust = clamp(self.trust + sign(score), -5, 5)
        return score


@dataclass
class World:
    month: int = 1
    safety: int = 3
    meaning: int = 1
    grief: int = 0
    obligations: int = 0
    isolation: int = 0
    supplies: int = 4
    events: List[str] = field(default_factory=list)
    people: Dict[str, Person] = field(default_factory=dict)

    @classmethod
    def new(cls) -> "World":
        return cls(people={
            "Mara": Person("Mara", {"medicine": 3, "safety": 1, "belonging": 2}),
            "Iven": Person("Iven", {"supplies": 2, "freedom": 3, "belonging": 1}),
        })

    def act(self, action: str):
        action = action.strip().lower()
        if action == "isolate":
            return self.isolate()
        if action == "visit mara":
            return self.connect("Mara")
        if action == "visit iven":
            return self.connect("Iven")
        if action == "share medicine":
            return self.share_medicine()
        if action == "take supplies":
            return self.take_supplies()
        raise ValueError(f"Unknown action: {action}")

    def isolate(self):
        self.safety += 2
        self.isolation += 2
        self.obligations = max(0, self.obligations - 1)
        self.meaning = max(0, self.meaning - 1)
        for person in self.people.values():
            if person.alive:
                person.closeness = max(0, person.closeness - 1)
                person.trust = max(-5, person.trust - 1)
                person.memories.append("You stayed away when contact was still possible.")
        event = "You barred the door. Nothing reached you. You reached no one."
        self.events.append(event)
        return self.snapshot(event)

    def connect(self, name: str):
        person = self.people[name]
        if not person.alive:
            event = f"You returned to {name}, but only the room remained."
            self.grief += max(1, person.closeness)
            self.events.append(event)
            return self.snapshot(event)
        self.safety = max(0, self.safety - 1)
        self.isolation = max(0, self.isolation - 1)
        self.meaning += 2
        self.obligations += 1
        person.closeness = clamp(person.closeness + 1, 0, 5)
        person.trust = clamp(person.trust + 1, -5, 5)
        help_received = 1 if person.trust >= 2 else 0
        self.supplies += help_received
        event = (f"You spent the evening with {name}. " +
                 ("They left you a bundle of supplies." if help_received else
                  "Nothing was solved, but neither of you was alone."))
        self.events.append(event)
        return self.snapshot(event)

    def share_medicine(self):
        changes = {"medicine": 1, "supplies": -1, "belonging": 1}
        self.supplies = max(0, self.supplies - 1)
        self.meaning += 1
        scores = {name: p.interpret(changes, "You") for name, p in self.people.items() if p.alive}
        event = "You gave the medicine to Mara. Mara saw care. Iven saw one fewer supply for the road."
        self.events.append(event)
        return self.snapshot(event, scores)

    def take_supplies(self):
        changes = {"supplies": -2, "safety": 1, "freedom": -1}
        self.supplies += 2
        self.safety += 1
        scores = {name: p.interpret(changes, "You") for name, p in self.people.items() if p.alive}
        event = "You took the shared supplies. Your shelter became safer. Someone else's road became harder."
        self.events.append(event)
        return self.snapshot(event, scores)

    def advance_month(self):
        self.month += 1
        mara = self.people["Mara"]
        if mara.alive and mara.trust <= -2 and self.month >= 3:
            mara.alive = False
            self.events.append("Mara died during the weeks when nobody knew how bad it had become.")
            if mara.closeness > 0:
                self.grief += mara.closeness
        if self.obligations > self.supplies:
            self.safety = max(0, self.safety - 1)
        return self.snapshot("Time passed. The world used the choices already made.")

    def snapshot(self, event: str, interpretations=None):
        return {
            "event": event,
            "month": self.month,
            "safety": self.safety,
            "meaning": self.meaning,
            "grief": self.grief,
            "obligations": self.obligations,
            "isolation": self.isolation,
            "supplies": self.supplies,
            "interpretations": dict(interpretations or {}),
            "people": {name: {"trust": p.trust, "closeness": p.closeness, "alive": p.alive}
                       for name, p in self.people.items()},
        }


def print_state(world: World):
    print(f"\nMonth {world.month} | Safety {world.safety} | Meaning {world.meaning} | "
          f"Grief {world.grief} | Isolation {world.isolation} | "
          f"Obligations {world.obligations} | Supplies {world.supplies}")
    for p in world.people.values():
        print(f"  {p.name}: {'alive' if p.alive else 'dead'}, trust {p.trust}, closeness {p.closeness}")


def main():
    world = World.new()
    print("=" * 64)
    print("THE DISTANCE BETWEEN US")
    print("Survival is possible. Winning is not implemented, because neither is life.")
    print("=" * 64)
    actions = ["isolate", "visit Mara", "visit Iven", "share medicine", "take supplies", "wait", "quit"]
    while True:
        print_state(world)
        print("\nActions:", ", ".join(actions))
        choice = input("> ").strip()
        if choice.lower() == "quit":
            break
        try:
            result = world.advance_month() if choice.lower() == "wait" else world.act(choice)
        except ValueError as exc:
            print(exc)
            continue
        print("\n" + result["event"])
        if result["interpretations"]:
            print("Interpretations:", result["interpretations"])


if __name__ == "__main__":
    main()