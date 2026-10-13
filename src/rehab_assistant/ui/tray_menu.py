"""Tray menu routes to the same tested manual posture actions as the window."""
import logging
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QMessageBox


def build_tray_menu(window, startup_provider, exit_callback):
    menu = QMenu(window)
    actions = {}

    def add(key, title, callback=None):
        action = QAction(title, menu)
        if callback:
            action.triggered.connect(callback)
        actions[key] = action
        menu.addAction(action)
        return action

    summary = add("status", "当前：尚未确认姿势")
    summary.setEnabled(False)
    menu.addSeparator()
    posture = window._posture
    up = add("up", "我已起身", lambda: window._run_posture_action(posture.confirm_up))
    sitting = add("sitting", "重新坐下", lambda: window._run_posture_action(posture.confirm_sitting))

    def toggle_tracking():
        callback = posture.resume_needs_confirmation if posture.state.posture == "PAUSED" else posture.pause
        window._run_posture_action(callback)

    pause = add("pause", "暂停追踪", toggle_tracking)
    menu.addSeparator()
    add("show", "打开主窗口", lambda: window.open_page("home"))
    add("settings", "设置", lambda: window.open_page("settings"))
    add("help", "帮助", lambda: window.open_page("info"))
    startup = add("startup", "登录时启动")
    startup.setCheckable(True)
    page = window._pages["settings"]

    def reflect_startup():
        try:
            enabled = startup_provider.is_enabled()
        except (OSError, ImportError):
            logging.getLogger(__name__).exception("Could not read login startup setting")
            startup.setEnabled(False)
            page.startup_check.setEnabled(False)
            page.startup_status.setText("无法读取当前用户登录启动设置；请检查本机日志")
            return
        for widget in (startup, page.startup_check):
            blocked = widget.blockSignals(True)
            widget.setChecked(enabled)
            widget.blockSignals(blocked)
            widget.setEnabled(True)
        page.startup_check.setToolTip("修改当前用户登录启动项，与系统托盘中的同名设置同步")
        page.startup_status.setText("登录启动已开启" if enabled else "登录启动已关闭")

    def toggle_startup(enabled):
        try:
            startup_provider.set_enabled(enabled)
        except (OSError, ImportError):
            logging.getLogger(__name__).exception("Could not update login startup setting")
            reflect_startup()
            page.startup_status.setText("登录启动设置未保存；已重新读取实际状态，请检查本机日志")
        else:
            reflect_startup()

    startup.triggered.connect(toggle_startup)
    page.startup_check.toggled.connect(toggle_startup)
    reflect_startup()
    menu.addSeparator()

    def confirm_exit():
        answer = QMessageBox.question(window, "退出腰椎康复助手", "退出后将停止计时和所有提醒。确认退出？",
                                      QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                      QMessageBox.StandardButton.No)
        if answer == QMessageBox.StandardButton.Yes:
            exit_callback()

    add("exit", "退出", confirm_exit)

    def refresh():
        state = posture.state.posture if posture else "UNKNOWN"
        title = {"UNKNOWN": "尚未确认姿势", "SITTING": "正在坐着", "UP": "已起身",
                 "PAUSED": "追踪已暂停", "NEEDS_CONFIRMATION": "中断后待核实"}[state]
        seconds = posture.elapsed_seconds() if posture else None
        if seconds is not None:
            title += f"（{'推算 ' if posture.state.uncertain else ''}{seconds // 60} 分钟）"
        summary.setText(f"当前：{title}")
        up.setEnabled(posture is not None and state not in ("UP", "PAUSED"))
        sitting.setEnabled(posture is not None and state in ("UP", "UNKNOWN"))
        pause.setEnabled(posture is not None)
        pause.setText("恢复并重新确认" if state == "PAUSED" else "暂停追踪")
        reflect_startup()

    menu.aboutToShow.connect(refresh)
    refresh()
    return menu, actions
