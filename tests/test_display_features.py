import unittest
from unittest import mock


class DisplayFeatureTests(unittest.TestCase):
    """捕获画面模式分组在迁移后丢失或映射错误。"""

    def test_picture_mode_group_maps_presets_to_primary_mode(self):
        from mimonitor_toolbox.display_features import DisplayFeaturesMixin

        host = object()
        self.assertEqual(DisplayFeaturesMixin._picture_mode_group_name(host, 64), "标准")
        self.assertEqual(DisplayFeaturesMixin._picture_mode_group_name(host, 25), "游戏")
        self.assertEqual(DisplayFeaturesMixin._picture_mode_group_name(host, 9), "电影")


class CrosshairModeReconcileTests(unittest.TestCase):
    """准星模式联动：离开游戏模式记住并隐藏，回到游戏模式还原。"""

    def _reconcile(self, vals, settings=None, connected=True, busy=False, last_mode=None):
        from mimonitor_toolbox import display_features
        from mimonitor_toolbox.display_features import DisplayFeaturesMixin

        settings = settings if settings is not None else {
            "crosshair_game_mode_only": True,
            "crosshair_memory": None,
        }
        applied = []

        class Host(DisplayFeaturesMixin):
            def __init__(self):
                self.current_vals = dict(vals)
                self.adb_connected = connected
                self._crosshair_reconcile_busy = busy
                if last_mode is not None:
                    self._crosshair_last_mode = last_mode

            def _apply_crosshair_mode_value(self, value, message):
                applied.append(value)
                self.current_vals["front_sight_index"] = value

            def _update_crosshair_mode_status_label(self):
                pass

        host = Host()
        with mock.patch.object(display_features, "load_settings", side_effect=lambda: dict(settings)), \
                mock.patch.object(display_features, "update_settings", side_effect=settings.update):
            host._reconcile_crosshair_mode_state()
        return applied, settings

    def test_leaving_game_mode_hides_crosshair_and_remembers_it(self):
        applied, settings = self._reconcile({
            "picture_mode": 14,
            "front_sight_index": 3,
        }, last_mode=10)

        self.assertEqual(applied, [0])
        self.assertEqual(settings["crosshair_memory"], 3)

    def test_entering_game_mode_restores_remembered_crosshair(self):
        applied, _ = self._reconcile(
            {"picture_mode": 10, "front_sight_index": 0},
            settings={"crosshair_game_mode_only": True, "crosshair_memory": 3},
            last_mode=14,
        )

        self.assertEqual(applied, [3])

    def test_game_mode_without_transition_does_not_restore(self):
        """用户用显示器 OSD 主动关掉准星后，不应被应用自动打开。"""
        applied, _ = self._reconcile(
            {"picture_mode": 10, "front_sight_index": 0},
            settings={"crosshair_game_mode_only": True, "crosshair_memory": 3},
            last_mode=10,
        )

        self.assertEqual(applied, [])

    def test_first_reconcile_after_connect_is_baseline_only(self):
        """首次对账只确立基线，不做还原（此前模式未知）。"""
        applied, _ = self._reconcile(
            {"picture_mode": 10, "front_sight_index": 0},
            settings={"crosshair_game_mode_only": True, "crosshair_memory": 3},
        )

        self.assertEqual(applied, [])

    def test_game_mode_keeps_user_choice_without_memory(self):
        applied, _ = self._reconcile({
            "picture_mode": 10,
            "front_sight_index": 5,
        }, last_mode=14)

        self.assertEqual(applied, [])

    def test_disabled_toggle_leaves_crosshair_alone(self):
        applied, _ = self._reconcile(
            {"picture_mode": 14, "front_sight_index": 3},
            settings={"crosshair_game_mode_only": False, "crosshair_memory": None},
            last_mode=10,
        )

        self.assertEqual(applied, [])

    def test_unknown_mode_or_value_is_skipped(self):
        for vals in (
            {"front_sight_index": 3},
            {"picture_mode": 14, "front_sight_index": None},
            {"picture_mode": 14, "front_sight_index": "N/A"},
            {"picture_mode": "null", "front_sight_index": 3},
        ):
            with self.subTest(vals=vals):
                applied, _ = self._reconcile(vals, last_mode=10)
                self.assertEqual(applied, [])

    def test_already_hidden_crosshair_is_not_rewritten(self):
        applied, settings = self._reconcile({
            "picture_mode": 9,
            "front_sight_index": 0,
        }, last_mode=10)

        self.assertEqual(applied, [])
        self.assertIsNone(settings["crosshair_memory"])

    def test_disconnected_device_is_skipped(self):
        applied, _ = self._reconcile(
            {"picture_mode": 14, "front_sight_index": 3},
            connected=False,
            last_mode=10,
        )

        self.assertEqual(applied, [])

    def test_busy_flag_blocks_reentrant_reconcile(self):
        applied, _ = self._reconcile(
            {"picture_mode": 14, "front_sight_index": 3},
            busy=True,
            last_mode=10,
        )

        self.assertEqual(applied, [])

    def test_manual_choice_updates_memory(self):
        from mimonitor_toolbox import display_features
        from mimonitor_toolbox.display_features import DisplayFeaturesMixin

        settings = {"crosshair_game_mode_only": True, "crosshair_memory": None}
        calls = []

        class Host(DisplayFeaturesMixin):
            def _set_game_feature(self, key, value, message, retrigger_game_mode=False):
                calls.append((key, value, retrigger_game_mode))

            def _update_crosshair_mode_status_label(self):
                pass

            def log(self, message):
                pass

        host = Host()
        with mock.patch.object(display_features, "load_settings", side_effect=lambda: dict(settings)), \
                mock.patch.object(display_features, "update_settings", side_effect=settings.update):
            host._fs(4)
            self.assertEqual(settings["crosshair_memory"], 4)
            host._fs(0)
            self.assertIsNone(settings["crosshair_memory"])

        self.assertEqual(
            calls,
            [
                ("front_sight_index", 4, True),
                ("front_sight_index", 0, True),
            ],
        )


if __name__ == "__main__":
    unittest.main()
