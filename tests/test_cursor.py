import sys
import unittest

from mouse_jiggler.cursor import WindowsCursorController


@unittest.skipUnless(sys.platform == "win32", "Только для Windows")
class WindowsCursorTests(unittest.TestCase):
    def test_position_and_virtual_screen_bounds_are_readable(self):
        cursor = WindowsCursorController()
        position = cursor.get_position()
        bounds = cursor.get_bounds()

        self.assertIsInstance(position.x, int)
        self.assertIsInstance(position.y, int)
        self.assertGreater(bounds.right, bounds.left)
        self.assertGreater(bounds.bottom, bounds.top)


if __name__ == "__main__":
    unittest.main()
