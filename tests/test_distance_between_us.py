import unittest
from holosim.distance_between_us import World


class DistanceBetweenUsTests(unittest.TestCase):
    def test_isolation_trades_meaning_for_safety(self):
        world = World.new()
        before = world.snapshot("before")
        world.act("isolate")
        self.assertGreater(world.safety, before["safety"])
        self.assertLess(world.meaning, before["meaning"])
        self.assertGreater(world.isolation, before["isolation"])
        self.assertLess(world.people["Mara"].trust, 0)

    def test_connection_creates_meaning_and_obligation(self):
        world = World.new()
        world.act("visit mara")
        self.assertEqual(world.meaning, 3)
        self.assertEqual(world.obligations, 1)
        self.assertEqual(world.people["Mara"].closeness, 1)
        self.assertEqual(world.safety, 2)

    def test_same_event_is_interpreted_by_need(self):
        world = World.new()
        result = world.act("share medicine")
        self.assertGreater(result["interpretations"]["Mara"], 0)
        self.assertLess(result["interpretations"]["Iven"], 0)

    def test_repeated_isolation_can_create_later_loss(self):
        world = World.new()
        world.act("visit mara")
        world.act("isolate")
        world.act("isolate")
        world.act("isolate")
        world.advance_month()
        world.advance_month()
        self.assertFalse(world.people["Mara"].alive)

    def test_no_global_good_or_evil_score(self):
        world = World.new()
        for attr in ("morality", "karma", "good", "evil"):
            self.assertFalse(hasattr(world, attr))


if __name__ == "__main__":
    unittest.main()