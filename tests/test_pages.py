import os
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QAbstractButton, QApplication

_qt_application = QApplication.instance() or QApplication([])


class PageContractTests(unittest.TestCase):
    """捕获页面方法遗漏或被重新散落到主窗口的回归。"""

    def test_all_page_builders_are_owned_by_pages_mixin(self):
        from mimonitor_toolbox.pages import PagesMixin

        expected = {
            "setup_ui",
            "_make_home_page",
            "_make_picture_page",
            "_make_game_page",
            "_make_source_page",
            "_make_light_page",
            "_make_tools_page",
            "_make_remote_page",
            "_add_slider",
            "_add_color_gain_slider",
            "_add_light_slider",
            "_btn_section",
        }

        self.assertTrue(expected.issubset(vars(PagesMixin)))

    def test_app_builds_all_pages_without_missing_module_dependencies(self):
        from mimonitor_toolbox.main_window import App

        with mock.patch.object(App, "register_global_hotkeys"), \
                mock.patch.object(App, "setup_tray"):
            window = App()

        expected = (
            "home_page",
            "picture_page",
            "game_page",
            "source_page",
            "light_page",
            "tools_page",
            "remote_page",
        )
        self.assertEqual(
            [name for name in expected if not hasattr(window, name)],
            [],
        )
        window._cleanup_done = True
        window.deleteLater()
        _qt_application.processEvents()

    def test_adb_cmd_and_shell_buttons_share_one_tool_card(self):
        from mimonitor_toolbox.main_window import App

        with mock.patch.object(App, "register_global_hotkeys"), \
                mock.patch.object(App, "setup_tray"):
            window = App()

        buttons = {
            button.text(): button
            for button in window.tools_page.findChildren(QAbstractButton)
        }
        self.assertIn("打开 ADB CMD", buttons)
        self.assertIn("进入 ADB Shell", buttons)
        self.assertIs(
            buttons["打开 ADB CMD"].parent(),
            buttons["进入 ADB Shell"].parent(),
        )
        window._cleanup_done = True
        window.deleteLater()
        _qt_application.processEvents()

    def test_non_game_mode_marks_game_feature_highlight_as_memory(self):
        from mimonitor_toolbox.main_window import App

        with mock.patch.object(App, "register_global_hotkeys"), \
                mock.patch.object(App, "setup_tray"):
            window = App()

        window._apply_polled_values({
            "picture_mode": 14,
            "picture_preset_scenario": 14,
            "front_sight_index": 0,
            "mt_game_dynamic_ft": 0,
            "mt_game_scope": 5,
            "mt_game_scope_night": 0,
        })

        hint = getattr(window, "game_mode_hint_label", None)
        self.assertIsNotNone(hint)
        self.assertIn("记忆值", hint.text())
        self.assertIn("当前未生效", hint.text())
        self.assertTrue(window.state_buttons["mt_game_scope"][5].isChecked())
        window._cleanup_done = True
        window.deleteLater()
        _qt_application.processEvents()

    def test_game_mode_marks_game_feature_highlight_as_current_value(self):
        from mimonitor_toolbox.main_window import App

        with mock.patch.object(App, "register_global_hotkeys"), \
                mock.patch.object(App, "setup_tray"):
            window = App()

        window._apply_polled_values({
            "picture_mode": 10,
            "picture_preset_scenario": 25,
            "front_sight_index": 1,
            "mt_game_dynamic_ft": 0,
            "mt_game_scope": 0,
            "mt_game_scope_night": 0,
        })

        hint = getattr(window, "game_mode_hint_label", None)
        self.assertIsNotNone(hint)
        self.assertIn("当前生效值", hint.text())
        window._cleanup_done = True
        window.deleteLater()
        _qt_application.processEvents()

    def test_crosshair_toggle_lives_in_tools_page_and_defaults_on(self):
        """准星联动开关放在软件设置页（不在游戏页），且默认开启。"""
        from mimonitor_toolbox import display_features
        from mimonitor_toolbox.main_window import App

        with mock.patch.object(display_features, "load_settings", return_value={
            "crosshair_game_mode_only": True,
            "crosshair_memory": None,
        }), mock.patch.object(App, "register_global_hotkeys"), \
                mock.patch.object(App, "setup_tray"):
            window = App()

        tools_toggles = {
            button.text(): button
            for button in window.tools_page.findChildren(QAbstractButton)
        }
        game_toggles = {
            button.text(): button
            for button in window.game_page.findChildren(QAbstractButton)
        }
        self.assertIn("准星仅在游戏模式下生效", tools_toggles)
        self.assertTrue(tools_toggles["准星仅在游戏模式下生效"].isChecked())
        self.assertNotIn("准星仅在游戏模式下生效", game_toggles)
        window._cleanup_done = True
        window.deleteLater()
        _qt_application.processEvents()

    def test_polled_non_game_mode_triggers_crosshair_reconcile(self):
        """用遥控器改模式（非应用发起）后，页面刷新数据时也要纠正准星。"""
        from mimonitor_toolbox import display_features
        from mimonitor_toolbox.main_window import App

        settings = {"crosshair_game_mode_only": True, "crosshair_memory": None}

        with mock.patch.object(App, "register_global_hotkeys"), \
                mock.patch.object(App, "setup_tray"):
            window = App()

        window.adb_connected = True
        with mock.patch.object(display_features, "load_settings", side_effect=lambda: dict(settings)), \
                mock.patch.object(display_features, "update_settings", side_effect=settings.update), \
                mock.patch.object(window, "_apply_crosshair_mode_value") as apply_value:
            window._apply_polled_values({
                "picture_mode": 14,
                "front_sight_index": 3,
            })

        apply_value.assert_called_once()
        self.assertEqual(apply_value.call_args[0][0], 0)
        self.assertEqual(settings["crosshair_memory"], 3)
        window._cleanup_done = True
        window.deleteLater()
        _qt_application.processEvents()


if __name__ == "__main__":
    unittest.main()
