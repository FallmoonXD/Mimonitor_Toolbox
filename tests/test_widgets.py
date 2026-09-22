import os
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QAbstractButton, QApplication, QTextEdit

_qt_application = QApplication.instance() or QApplication([])


class _StubMoveEvent:
    """够 mouseMoveEvent 用的假事件：只要 globalPosition().toPoint()。"""

    def __init__(self, global_pos):
        self._global_pos = global_pos

    def globalPosition(self):
        outer = self

        class _Pos:
            def toPoint(self):
                return outer._global_pos

        return _Pos()


class WidgetConstructionTests(unittest.TestCase):
    """捕获仅在对话框构造时才暴露的控件依赖遗漏。"""

    def test_close_confirmation_dialog_constructs(self):
        from mimonitor_toolbox.widgets import CloseConfirmDialog

        dialog = CloseConfirmDialog()
        self.assertIsNotNone(dialog.chk_remember)
        dialog.deleteLater()
        _qt_application.processEvents()

    def test_new_log_scrolls_to_bottom_when_text_cursor_is_in_middle(self):
        from mimonitor_toolbox import adb as adb_runtime
        from mimonitor_toolbox.main_window import App

        log_widget = QTextEdit()
        log_widget.resize(400, 220)
        log_widget.show()
        for index in range(200):
            log_widget.append(f"line {index}")
        _qt_application.processEvents()

        cursor = log_widget.textCursor()
        cursor.setPosition(log_widget.document().characterCount() // 2)
        log_widget.setTextCursor(cursor)
        scroll_bar = log_widget.verticalScrollBar()
        scroll_bar.setValue(scroll_bar.maximum())

        fake_app = type("FakeApp", (), {"log_widget": log_widget})()
        with mock.patch.object(adb_runtime, "_log_file", None):
            App._on_log(fake_app, "new log")
        _qt_application.processEvents()

        self.assertEqual(scroll_bar.value(), scroll_bar.maximum())
        log_widget.close()
        log_widget.deleteLater()
        _qt_application.processEvents()


class TraySliderRowTests(unittest.TestCase):
    """浮条卡片的内容一行：图标 + 名称 + 滑杆（数值不画在这一行）。"""

    def _row(self, on_change=None, step=None, minimum=1, maximum=100, value=40):
        from mimonitor_toolbox.widgets import TraySliderRow

        captured = on_change if on_change is not None else []
        callback = captured.append if isinstance(captured, list) else captured
        row = TraySliderRow(
            None, "背光", minimum, maximum, value,
            on_change=callback, step=step, entry_id="backlight",
        )
        return row, captured

    def test_用真实滑动条控件且单行(self):
        from qfluentwidgets import Slider

        row, _ = self._row()
        self.assertIsInstance(row.slider, Slider)
        self.assertEqual(row.slider.orientation(), Qt.Orientation.Horizontal)
        self.assertEqual(row.value(), 40)
        self.assertEqual(row.slider.value(), 40)
        self.assertLessEqual(row.height(), 56)  # 一行
        row.deleteLater()

    def test_数值不画在这一行(self):
        """需求：数值只留在托盘菜单那一行条目上，卡片只有图标 + 名称 + 滑杆。"""
        from qfluentwidgets import BodyLabel

        row, _ = self._row()
        labels = row.findChildren(BodyLabel)
        self.assertEqual(len(labels), 1, "卡片里只该有名称这一个文字控件")
        self.assertEqual(labels[0].text(), "背光")
        row.deleteLater()

    def test_数值跟手_不被步长吸附到同一档(self):
        """回归：以前拖动时按快捷键的 step 做吸附网格，94~98 全被拽回 96、
        99~100 又跳到 100，于是「96 和 100 视觉一样但实际值不同」，手柄还一直弹。
        现在与主窗口页面滑杆一致：连续取值，手柄跟手。"""
        row, captured = self._row(step=5, minimum=1, maximum=100)
        for value in (94, 95, 96, 97, 98, 99, 100):
            row.slider.setValue(value)
            _qt_application.processEvents()
            self.assertEqual(row.value(), value, f"{value} 被吸附走了")
            self.assertEqual(row.slider.value(), value, f"手柄被拽离了 {value}")
        self.assertEqual(captured[-1], 100)
        row.deleteLater()

    def test_set_value_原样写入不吸附(self):
        """设备读回的当前值未必是步长整数倍，显示要与真实值一致。"""
        row, _ = self._row(step=5)
        row.set_value(42, notify=False)
        self.assertEqual(row.value(), 42)
        self.assertEqual(row.slider.value(), 42)
        row.set_value(3, notify=False)
        self.assertEqual(row.value(), 3)
        row.deleteLater()

    def test_set_value_不触发回调(self):
        row, captured = self._row()
        row.set_value(70, notify=False)
        self.assertEqual(captured, [])
        row.deleteLater()

    def test_未连接时滑杆禁用并压暗(self):
        row, _ = self._row()
        row.set_connected(False)
        self.assertFalse(row.slider.isEnabled())
        self.assertIsNotNone(row._dim_effect)
        self.assertAlmostEqual(row._dim_effect.opacity(), row.DISCONNECTED_OPACITY)

        row.set_connected(True)
        self.assertTrue(row.slider.isEnabled())
        self.assertIsNone(row.graphicsEffect())
        row.deleteLater()


class TraySliderCardTests(unittest.TestCase):
    """悬停弹出的圆角浮条：机制是子菜单（Qt Popup 链），视觉是一行卡片。"""

    def _card(self, value=42, maximum=100, step=5):
        from mimonitor_toolbox.widgets import TraySliderCard

        captured = []
        card = TraySliderCard(
            None, "背光", 1, maximum, value,
            on_change=lambda eid, v: captured.append((eid, v)),
            step=step, entry_id="backlight",
        )
        return card, captured

    def _close(self, card):
        """删掉卡片并**立刻**回收。

        卡片是 RoundMenu，view 上挂着 QGraphicsDropShadowEffect。把多张卡片的
        deleteLater 攒到同一轮事件循环里集中回收，Windows 上会踩到访问违例
        （0xC0000005，表现为进程直接死、没有 traceback）。同一文件里
        WidgetConstructionTests 也是 deleteLater 后马上 processEvents，
        照这个约定来。
        """
        card.deleteLater()
        _qt_application.processEvents()

    def test_卡片只有一行内容(self):
        from mimonitor_toolbox.widgets import TraySliderRow

        card, _ = self._card()
        self.assertEqual(card.view.count(), 1)
        item = card.view.item(0)
        self.assertIs(card.view.itemWidget(item), card.row)
        self.assertIsInstance(card.row, TraySliderRow)
        self.assertEqual(item.flags(), Qt.ItemFlag.NoItemFlags,
                         "滑杆自己收鼠标，条目不该可点选")
        self.assertEqual(card.row.width(), TraySliderRow.CARD_WIDTH)
        self._close(card)

    def test_点击浮条不关掉父菜单(self):
        """基类 mousePressEvent 对 view 之外的点击会 _hideMenu(True)，再经
        hideEvent（isHideBySystem 且 isSubMenu）**级联关掉父菜单** —— 而那
        往往只是点到圆角外的阴影留白。卡片只承载滑杆，一律吞掉。
        """
        card, _ = self._card()
        with mock.patch.object(card, "_hideMenu") as hide_menu:
            card.mousePressEvent(None)
        hide_menu.assert_not_called()
        self._close(card)

    def test_exec_强制无动画(self):
        from qfluentwidgets import MenuAnimationType, RoundMenu

        card, _ = self._card()
        with mock.patch.object(RoundMenu, "exec", return_value=None) as parent_exec:
            card.exec(QPoint(10, 10))
        self.assertEqual(
            parent_exec.call_args.kwargs.get("aniType"), MenuAnimationType.NONE
        )
        # 库里 exec 的 ani 形参没被真正使用，所以也不该再传它
        self.assertNotIn("ani", parent_exec.call_args.kwargs)
        self.assertEqual(parent_exec.call_args.args[0], QPoint(10, 10),
                         "位置原样交给基类，由 _endPosition 做 margin 回抵")
        self._close(card)

    def test_菜单行文字随数值同步(self):
        from qfluentwidgets import RoundMenu

        card, captured = self._card(value=42)
        parent = RoundMenu("托盘")
        parent.addMenu(card)
        self.assertEqual(card.menuItem.text().strip(), "背光   42")

        card.row.slider.setValue(51)  # min=1 step=5，51 在网格上
        _qt_application.processEvents()

        self.assertEqual(card.menuItem.text().strip(), "背光   51",
                         "拖动时数值要实时跟到托盘那一行")
        self.assertEqual(captured, [("backlight", 51)])
        parent.deleteLater()
        _qt_application.processEvents()

    def test_行宽按最宽数值预留_拖动不重排(self):
        """行宽若跟着数值变，菜单会在拖动中重排抖动，位数变多时还会被裁。"""
        from qfluentwidgets import RoundMenu

        card, _ = self._card(value=42, maximum=100)
        parent = RoundMenu("托盘")
        parent.addMenu(card)
        font_metrics = parent.view.fontMetrics()

        widths = []
        for value in (1, 9, 42, 99, 100):
            card.row.slider.setValue(value)
            widths.append(card.menuItem.sizeHint().width())
            self.assertGreaterEqual(
                card.menuItem.sizeHint().width(),
                font_metrics.boundingRect(card.menuItem.text()).width(),
                f"{card.menuItem.text()!r} 装不进预留行宽",
            )
        self.assertEqual(len(set(widths)), 1,
                         f"拖动过程中行宽应恒定，实测 {widths}")
        parent.deleteLater()
        _qt_application.processEvents()

    def test_断连时浮条同步置灰(self):
        card, _ = self._card()
        card.set_connected(False)
        self.assertFalse(card.row.slider.isEnabled())
        self.assertIsNotNone(card.row._dim_effect)

        card.set_connected(True)
        self.assertTrue(card.row.slider.isEnabled())
        self._close(card)

    def test_离开本行进入宽限期_不立刻收起(self):
        """回归：从菜单移到卡片要穿过行外那几像素 + 定位留的 5px 间隙。基类
        一离开本行就收，浮条于是闪没、约 400ms 后又弹回来（「鼠标放上去会抖」）。"""
        card, _ = self._card()
        with mock.patch.object(card, "_hideMenu") as hide_menu:
            card.mouseMoveEvent(_StubMoveEvent(QPoint(-500, -500)))
            hide_menu.assert_not_called()
            self.assertTrue(card._hide_timer.isActive(), "应进入宽限等待")

            # 指针落到卡片上：取消待收起
            card.mouseMoveEvent(_StubMoveEvent(card.mapToGlobal(QPoint(0, 0))))
            self.assertFalse(card._hide_timer.isActive())
            _qt_application.processEvents()
        hide_menu.assert_not_called()
        self._close(card)

    def test_宽限期满且指针不在附近才收起(self):
        card, _ = self._card()
        with mock.patch.object(card, "_point_on_card", return_value=False), \
                mock.patch.object(card, "_point_on_own_row", return_value=False), \
                mock.patch.object(card, "_hideMenu") as hide_menu:
            card._hide_after_grace()
        hide_menu.assert_called_once_with(False)

        # 指针还在卡片或本行上则不收
        with mock.patch.object(card, "_point_on_card", return_value=True), \
                mock.patch.object(card, "_hideMenu") as hide_menu2:
            card._hide_after_grace()
        hide_menu2.assert_not_called()
        self._close(card)


if __name__ == "__main__":
    unittest.main()
