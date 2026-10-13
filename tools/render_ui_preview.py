"""Render deterministic UI fixtures, never read or change the user's data.

This is a presentation check, not proof of Windows notifications/sleep handling.
"""

import argparse
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/ui"))
    parser.add_argument("--platform", choices=("offscreen", "windows"), default="offscreen")
    parser.add_argument("--scale", type=float, default=1)
    args = parser.parse_args()
    os.environ["QT_QPA_PLATFORM"] = args.platform
    os.environ["QT_SCALE_FACTOR"] = str(args.scale)

    from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QWidget
    from rehab_assistant.app import MainWindow
    from rehab_assistant.services.posture_service import PostureService
    from rehab_assistant.services.reminder_service import ReminderService
    from rehab_assistant.storage.database import migrate

    class PreviewClock:
        ticks = 0

        def now(self):
            return datetime(2026, 10, 13, 8, tzinfo=timezone.utc) + timedelta(seconds=self.ticks)

        def monotonic(self):
            return self.ticks

    class SilentChannel:
        def notify(self, reminder):
            pass  # Never emit OS notifications from preview fixtures.

    app = QApplication([])
    args.output_dir.mkdir(parents=True, exist_ok=True)
    cases = (
        ("unknown", 0, (1040, 780), False),
        ("sitting", 28 * 60 + 15, (1040, 780), False),
        ("warning", 35 * 60, (1040, 780), False),
        ("limit", 41 * 60 + 8, (1040, 780), False),
        ("confirmation", 600, (1040, 780), True),
        ("narrow", 55 * 60, (520, 740), False),
        ("long", 6000 * 60 + 12, (520, 740), False),
    )
    for name, seconds, size, interrupted in cases:
        connection = sqlite3.connect(":memory:")
        migrate(connection)
        clock = PreviewClock()
        posture = PostureService(connection, clock)
        if seconds:
            posture.confirm_sitting()
            clock.ticks = seconds
        if interrupted:
            posture.observe_environment("sleep_started")
        reminders = ReminderService(connection, posture, SilentChannel(), clock=clock)
        tray = QSystemTrayIcon()
        window = MainWindow(tray, posture, reminders)
        window._refresh_timer.stop()
        window.resize(*size)
        window.show()
        app.processEvents()
        path = args.output_dir / f"{name}.png"
        if not window.grab().save(str(path)):
            raise RuntimeError(f"Could not save {path}")
        if window.centralWidget().horizontalScrollBar().maximum():
            for widget in window.centralWidget().findChildren(QWidget):
                if widget.isVisible() and widget.minimumSizeHint().width() > 280:
                    print("layout-diagnostic:", type(widget).__name__, widget.objectName(),
                          widget.minimumSizeHint(), widget.size(), getattr(widget, "text", lambda: "")())
        assert window.centralWidget().horizontalScrollBar().maximum() == 0, (
            name, window.size(), window.centralWidget().viewport().size(),
            window.centralWidget().widget().minimumSizeHint(),
            window.centralWidget().horizontalScrollBar().maximum(),
        )
        print(f"{name}: platform={app.platformName()} scale={window.devicePixelRatioF()} "
              f"visible={window.isVisible()} screenshot={path.resolve()}")
        if name == "sitting":
            for key in ("record", "training", "chart", "settings", "info"):
                window.show_page(key)
                app.processEvents()
                assert window.centralWidget().horizontalScrollBar().maximum() == 0, key
                page_path = args.output_dir / f"page-{key}.png"
                assert window.centralWidget().widget().grab().save(str(page_path))
                print(f"page-{key}: full scroll-content screenshot={page_path.resolve()}")
                if key in ("training", "chart"):
                    tabs = window._pages[key].tab_widget
                    for index in range(1, tabs.count()):
                        tabs.setCurrentIndex(index)
                        app.processEvents()
                        assert window.centralWidget().widget().grab().save(str(args.output_dir / f"page-{key}-tab{index}.png"))
                    tabs.setCurrentIndex(0)
            from rehab_assistant.ui.pages import preview_dialog
            for kind in ("startup", "warning", "limit"):
                dialog = preview_dialog(window, kind)
                app.processEvents()
                assert dialog.grab().save(str(args.output_dir / f"preview-{kind}.png"))
                dialog.close()
            from rehab_assistant.ui.tray_menu import build_tray_menu
            from PySide6.QtCore import QPoint
            class PreviewStartup:
                def is_enabled(self):
                    return False
                def set_enabled(self, enabled):
                    raise RuntimeError("Preview must never write Windows startup settings")
            menu, _ = build_tray_menu(window, PreviewStartup(), lambda: None)
            menu.popup(window.mapToGlobal(QPoint(60, 60)))
            app.processEvents()
            assert menu.grab().save(str(args.output_dir / "tray-menu.png"))
            menu.close()
            window.resize(520, 740)
            for key in window._pages:
                window.show_page(key)
                app.processEvents()
                assert window.centralWidget().horizontalScrollBar().maximum() == 0, ("narrow", key, window.size(), window.centralWidget().widget().minimumSizeHint(), window.centralWidget().horizontalScrollBar().maximum())
                assert window.grab().save(str(args.output_dir / f"page-{key}-narrow.png"))
            window.show_page("home")
        window.close()
        window.deleteLater()
        app.processEvents()
        connection.close()


if __name__ == "__main__":
    main()
