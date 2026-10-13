"""Windows tray notification adapter."""

from __future__ import annotations

from PySide6.QtWidgets import QSystemTrayIcon

from rehab_assistant.services.reminder_service import Reminder


class TrayNotificationChannel:
    """Use the Qt tray API without conflating delivery with user acknowledgement."""

    def __init__(self, tray: QSystemTrayIcon) -> None:
        self._tray = tray

    def notify(self, reminder: Reminder) -> None:
        if reminder.threshold_minutes >= 2:
            title = "坐姿已达到 40 分钟"
            body = "请尽快改变姿势或起身活动；提醒仍需由你确认。"
            icon = QSystemTrayIcon.MessageIcon.Warning
        else:
            title = "坐姿已达到 35 分钟"
            body = "建议现在改变姿势或起身活动。"
            icon = QSystemTrayIcon.MessageIcon.Information
        self._tray.showMessage(title, body, icon, 10000)
