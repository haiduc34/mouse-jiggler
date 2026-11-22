import tkinter as tk
import unittest

from mouse_jiggler.app import MouseJigglerApp
from mouse_jiggler.cursor import Point, ScreenBounds


class FakeCursor:
    def get_position(self):
        return Point(100, 100)

    def get_bounds(self):
        return ScreenBounds(0, 0, 500, 500)

    def move_to(self, point):
        pass


class AppTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            self.skipTest(f"Графический дисплей недоступен: {error}")
        self.root.withdraw()
        self.app = MouseJigglerApp(self.root, cursor_factory=FakeCursor)

    def tearDown(self):
        self.app.close()

    def test_initial_window_and_button_state(self):
        self.assertEqual(self.root.title(), "Mouse Jiggler")
        self.assertTrue(self.root.overrideredirect())
        self.assertEqual(self.app.title_label.cget("text"), "Mouse Jiggler")
        self.assertEqual(self.app.title_label.pack_info()["anchor"], "center")
        self.assertFalse(self.root.resizable()[0])
        self.assertFalse(self.root.resizable()[1])
        self.assertEqual(
            self.app.movement_button.cget("text"), "Mouse Jiggler не действует"
        )
        self.assertEqual(self.app.return_button.cget("text"), "Возвращать курсор")

        self.root.deiconify()
        self.root.update()
        self.assertEqual((self.root.winfo_width(), self.root.winfo_height()), (450, 140))
        self.assertLessEqual(self.root.winfo_reqwidth(), 450)
        self.assertLessEqual(self.root.winfo_reqheight(), 140)
        self.root.withdraw()

    def test_compact_layout_places_controls_beside_their_fields(self):
        movement_grid = self.app.movement_button.grid_info()
        return_grid = self.app.return_button.grid_info()
        controls_grid = self.app.window_controls.grid_info()
        minimize_grid = self.app.minimize_button.grid_info()
        close_grid = self.app.close_button.grid_info()

        self.assertEqual((movement_grid["row"], movement_grid["column"]), (1, 2))
        self.assertEqual((return_grid["row"], return_grid["column"]), (2, 2))
        self.assertEqual((controls_grid["row"], controls_grid["column"]), (3, 2))
        self.assertEqual((minimize_grid["row"], minimize_grid["column"]), (0, 0))
        self.assertEqual((close_grid["row"], close_grid["column"]), (0, 1))
        self.assertEqual(self.app.minimize_button.cget("text"), "Свернуть")
        self.assertEqual(self.app.entries["move_interval_ms"].cget("width"), 5)
        self.assertEqual(self.app.entries["return_interval_ms"].cget("width"), 5)
        self.assertIn("e", close_grid["sticky"])
        self.assertIn("w", close_grid["sticky"])

    def test_minimize_and_restore_preserve_borderless_window(self):
        self.root.deiconify()
        self.root.update()
        self.app.minimize()
        self.root.update()
        self.assertEqual(self.root.state(), "iconic")

        self.root.deiconify()
        self.root.update()
        self.assertNotEqual(self.root.state(), "iconic")
        self.assertTrue(self.root.overrideredirect())
        self.assertIsNone(self.app._map_binding)
        self.root.withdraw()

    def test_all_fields_limit_input_to_four_characters(self):
        for entry in self.app.entries.values():
            entry.delete(0, tk.END)
            for character in "12345":
                entry.insert(tk.END, character)
            self.assertEqual(entry.get(), "1234")

        distance = self.app.entries["distance"]
        distance.delete(0, tk.END)
        for character in "-1234":
            distance.insert(tk.END, character)
        self.assertEqual(distance.get(), "-123")

    def test_return_toggle_disables_its_interval_field(self):
        self.app.toggle_return()
        self.assertEqual(
            self.app.entries["return_interval_ms"].cget("state"), "disabled"
        )
        self.assertEqual(
            self.app.return_button.cget("text"), "Не возвращать курсор"
        )

        self.app.toggle_return()
        self.assertEqual(
            self.app.entries["return_interval_ms"].cget("state"), "normal"
        )

    def test_field_commit_updates_normalized_settings(self):
        self.app.variables["move_interval_ms"].set("-2500.9")
        self.app._commit("move_interval_ms")
        self.assertEqual(self.app.settings.snapshot().move_interval_ms, 2500)
        self.assertEqual(self.app.variables["move_interval_ms"].get(), "2500")

    def test_movement_can_start_and_stop_without_real_mouse_access(self):
        self.app.toggle_movement()
        self.assertTrue(self.app._engine.is_running)
        self.assertEqual(
            self.app.movement_button.cget("text"), "Mouse Jiggler действует"
        )

        self.app.toggle_movement()
        self.assertFalse(self.app._engine.is_running)
        self.assertEqual(
            self.app.movement_button.cget("text"), "Mouse Jiggler не действует"
        )


if __name__ == "__main__":
    unittest.main()
