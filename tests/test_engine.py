import unittest

from mouse_jiggler.cursor import Point, ScreenBounds
from mouse_jiggler.engine import JiggleEngine, choose_target
from mouse_jiggler.model import JigglerSettings, SettingsStore


class FakeCursor:
    def __init__(self, position=Point(100, 100)):
        self.position = position
        self.bounds = ScreenBounds(0, 0, 500, 500)
        self.moves = []

    def get_position(self):
        return self.position

    def get_bounds(self):
        return self.bounds

    def move_to(self, point):
        self.position = point
        self.moves.append(point)


class ScriptedEngine(JiggleEngine):
    """Run the worker synchronously with deterministic waits."""

    def __init__(self, settings, cursor, stop_after, on_wait=None):
        super().__init__(settings, cursor)
        self.stop_after = stop_after
        self.on_wait = on_wait
        self.waits = []

    def _wait_for(self, milliseconds):
        self.waits.append(milliseconds)
        if self.on_wait:
            self.on_wait(len(self.waits))
        if len(self.waits) >= self.stop_after:
            self._stop_event.set()
        return True


class ChooseTargetTests(unittest.TestCase):
    def setUp(self):
        self.bounds = ScreenBounds(0, 0, 500, 500)

    def test_only_feasible_directions_are_offered(self):
        offered = []

        def choose(directions):
            offered.extend(directions)
            return directions[0]

        target = choose_target(Point(0, 499), 10, self.bounds, choose)
        self.assertEqual(offered, ["right", "up"])
        self.assertEqual(target, Point(10, 499))

    def test_non_virtual_origin_and_exclusive_edges(self):
        bounds = ScreenBounds(-500, -300, 100, 200)
        offered = []
        choose_target(
            Point(99, 199),
            2,
            bounds,
            lambda directions: offered.extend(directions) or directions[0],
        )
        self.assertEqual(offered, ["left", "up"])

    def test_impossible_full_distance_move_is_skipped(self):
        origin = Point(0, 0)
        self.assertEqual(choose_target(origin, 1000, self.bounds), origin)


class EngineTests(unittest.TestCase):
    def test_move_and_return(self):
        cursor = FakeCursor()
        settings = SettingsStore(
            JigglerSettings(move_interval_ms=20, return_interval_ms=30, distance=10)
        )
        engine = ScriptedEngine(settings, cursor, stop_after=2)
        engine._run()

        self.assertEqual(engine.waits, [20, 30])
        self.assertEqual(len(cursor.moves), 2)
        self.assertEqual(
            abs(cursor.moves[0].x - 100) + abs(cursor.moves[0].y - 100), 10
        )
        self.assertEqual(cursor.moves[-1], Point(100, 100))
        self.assertEqual(cursor.position, Point(100, 100))

    def test_return_is_cancelled_if_cursor_was_moved_by_user(self):
        cursor = FakeCursor()

        def on_wait(wait_number):
            if wait_number == 2:
                cursor.position = Point(300, 300)

        engine = ScriptedEngine(
            SettingsStore(), cursor, stop_after=2, on_wait=on_wait
        )
        engine._run()

        self.assertEqual(len(cursor.moves), 1)
        self.assertEqual(cursor.position, Point(300, 300))

    def test_return_can_be_disabled_during_wait(self):
        cursor = FakeCursor()
        settings = SettingsStore()

        def on_wait(wait_number):
            if wait_number == 2:
                settings.update(return_cursor=False)

        engine = ScriptedEngine(
            settings, cursor, stop_after=2, on_wait=on_wait
        )
        engine._run()

        self.assertEqual(len(cursor.moves), 1)
        self.assertNotEqual(cursor.position, Point(100, 100))


if __name__ == "__main__":
    unittest.main()
