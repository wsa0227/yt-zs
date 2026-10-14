"""Desktop presentation of existing posture/reminder services."""

from __future__ import annotations

import logging
from datetime import datetime

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QColor, QCloseEvent
from PySide6.QtWidgets import (
    QBoxLayout, QFrame, QHBoxLayout, QLabel, QMainWindow, QPushButton,
    QScrollArea, QSystemTrayIcon, QVBoxLayout, QWidget,
    QGraphicsDropShadowEffect, QComboBox,
)

from rehab_assistant import APP_NAME, APP_SLOGAN
from rehab_assistant.services.posture_service import PostureService
from rehab_assistant.services.reminder_service import ReminderService
from .components import card, label
from .pages import FeatureStrip, build_pages
from .theme import COLORS, stylesheet
from .widgets import Illustration, ThresholdRing, brand_icon, icon


def set_property(widget, key, value):
    # Re-polish only when a semantic state changes, not every timer tick.
    if widget.property(key) != value:
        widget.setProperty(key, value)
        widget.style().unpolish(widget)
        widget.style().polish(widget)
        widget.updateGeometry()
        widget.update()


def clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            # Hidden immediately: deleteLater alone can leave stale focused buttons.
            item.widget().hide()
            item.widget().deleteLater()


class MainWindow(QMainWindow):
    def __init__(
        self,
        tray: QSystemTrayIcon,
        posture: PostureService | None = None,
        reminders: ReminderService | None = None,
        environment=None,
        symptom_service=None,
        training_service=None,
        statistics_service=None,
    ) -> None:
        super().__init__()
        self._tray, self._posture = tray, posture
        self._reminders, self._environment = reminders, environment
        self._symptom_service = symptom_service
        self._training_service = training_service
        self._statistics_service = statistics_service
        self._rendered_posture = None
        self._rendered_reminders = None
        self._allow_exit = False
        self._layout_settler = QTimer(self)
        self._layout_settler.setSingleShot(True)
        self._layout_settler.timeout.connect(self._settle_layout)
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(brand_icon())
        self.setMinimumSize(520, 540)
        self.resize(1040, 780)
        self.setStyleSheet(stylesheet())
        self._build_ui()
        self._refresh_timer = QTimer(self)
        self._refresh_timer.timeout.connect(self._refresh_posture)
        self._refresh_timer.start(1000)
        self._refresh_posture()

    def _build_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setCentralWidget(scroll)
        shell = QWidget()
        shell.setObjectName("shell")
        shell_layout = QHBoxLayout(shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)
        scroll.setWidget(shell)
        self._build_sidebar(shell_layout)

        page = QWidget()
        page.setObjectName("page")
        shell_layout.addWidget(page, 1)
        self._body_layout = QVBoxLayout(page)
        self._body_layout.setContentsMargins(0, 0, 0, 0)
        self._compact_navigation = QComboBox()
        self._compact_navigation.addItems([title for _, title in self._nav_buttons])
        self._compact_navigation.setAccessibleName("页面导航")
        self._compact_navigation.currentIndexChanged.connect(
            lambda index: self.show_page(("home", "record", "training", "chart", "settings", "info")[index]))
        self._compact_navigation.hide()
        self._body_layout.addWidget(self._compact_navigation)
        self._home_page = QWidget()
        self._body_layout.addWidget(self._home_page)
        self._current_page = "home"
        self._pages = {"home": self._home_page}
        self._page_layout = QVBoxLayout(self._home_page)
        self._page_layout.setContentsMargins(24, 24, 24, 20)
        self._page_layout.setSpacing(16)

        self._page_layout.addWidget(label("科学提醒 · 记录健康 · 坚持改变", role="section"))
        self._features = FeatureStrip(self.show_page)
        self._page_layout.addWidget(self._features)

        self._hero, hero = card("timerCard")
        hero.setContentsMargins(20, 20, 20, 20)
        hero.setSpacing(12)
        shadow = QGraphicsDropShadowEffect(self._hero)
        shadow.setBlurRadius(18)
        shadow.setOffset(0, 3)
        shadow.setColor(QColor(31, 72, 120, 14))
        self._hero.setGraphicsEffect(shadow)
        self._page_layout.addWidget(self._hero)
        heading = QHBoxLayout()
        heading.addWidget(label("当前状态", role="section"))
        info = QLabel()
        info.setPixmap(icon("info", COLORS["muted"]).pixmap(18, 18))
        info.setToolTip("姿势由你人工确认；键鼠活动不用于判断真实坐姿或起身。")
        heading.addWidget(info)
        heading.addStretch()
        hero.addLayout(heading)

        self._content_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self._content_layout.setSpacing(24)
        hero.addLayout(self._content_layout)
        self._ring_panel = QWidget()
        ring_panel_layout = QVBoxLayout(self._ring_panel)
        ring_panel_layout.setContentsMargins(0, 0, 0, 0)
        self._track = ThresholdRing()
        ring_panel_layout.addWidget(self._track, 0, Qt.AlignmentFlag.AlignCenter)
        ring_layout = QVBoxLayout(self._track)
        self._ring_layout = ring_layout
        ring_layout.setContentsMargins(36, 48, 36, 48)
        ring_layout.setSpacing(2)
        self._posture_art = Illustration("brand.svg")
        self._posture_art.setFixedSize(110, 90)
        self._posture_art.setToolTip("装饰插画，非姿势检测结果")
        ring_layout.addWidget(self._posture_art, 0, Qt.AlignmentFlag.AlignCenter)
        self._timer_caption = label("本次坐姿 · 经过时间", role="muted")
        self._timer_caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ring_layout.addWidget(self._timer_caption)
        self._elapsed = label("--:--", name="elapsed")
        self._elapsed.setWordWrap(False)
        self._elapsed.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._elapsed.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        ring_layout.addWidget(self._elapsed)
        self._countdown = label("等待人工确认", role="muted")
        self._countdown.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ring_layout.addWidget(self._countdown)
        self._content_layout.addWidget(self._ring_panel)

        self._details = QWidget()
        details = QVBoxLayout(self._details)
        details.setContentsMargins(0, 8, 0, 8)
        details.setSpacing(12)
        details.addStretch()
        status = QHBoxLayout()
        status.setSpacing(8)
        status.addWidget(label("当前：", role="section"))
        self._summary = label(name="statusBadge")
        status.addWidget(self._summary)
        self._status_dot = QLabel()
        self._status_dot.setObjectName("statusDot")
        self._status_dot.setFixedSize(10, 10)
        status.addWidget(self._status_dot)
        status.addStretch()
        details.addLayout(status)
        self._started_at = label("尚无已确认的坐姿开始时间", role="muted")
        details.addWidget(self._started_at)
        self._headline = label(name="headline")
        details.addWidget(self._headline)
        self._time_context = label(role="muted")
        details.addWidget(self._time_context)
        self._actions = QWidget()
        self._action_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight, self._actions)
        self._action_layout.setContentsMargins(0, 0, 0, 0)
        self._action_layout.setSpacing(8)
        details.addWidget(self._actions)
        details.addStretch()
        self._content_layout.addWidget(self._details, 1)
        self._notice = label(name="notice")
        hero.addWidget(self._notice)
        rule = label("35 分钟提醒 / 40 分钟上限 · 不必坐满；键鼠活动不代表起身。", role="muted")
        hero.addWidget(rule)
        self._error_message = label(name="errorMessage")
        self._error_message.hide()
        hero.addWidget(self._error_message)

        self._stats_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self._stats_layout.setSpacing(12)
        self._page_layout.addLayout(self._stats_layout)
        self._next_value, self._next_hint = self._stat_card("bell", "下一个提醒", "等待确认", "35 / 40 分钟")
        self._today_time, self._today_time_hint = self._stat_card("clock", "今日坐姿时长", "—", "统计功能尚未开放")
        self._today_up, self._today_up_hint = self._stat_card("up", "今日起身次数", "—", "统计功能尚未开放")

        self._side_panel, reminder_layout = card("reminderCard")
        self._page_layout.addWidget(self._side_panel)
        heading = QHBoxLayout()
        heading.addWidget(label("待处理提醒", role="section"), 1)
        self._reminder_count = label("0 条", role="muted")
        heading.addWidget(self._reminder_count)
        reminder_layout.addLayout(heading)
        self._reminder_empty = label("暂无待处理提醒", role="muted")
        reminder_layout.addWidget(self._reminder_empty)
        self._reminder_actions = QWidget()
        self._reminder_layout = QVBoxLayout(self._reminder_actions)
        self._reminder_layout.setContentsMargins(0, 0, 0, 0)
        self._reminder_layout.setSpacing(8)
        reminder_layout.addWidget(self._reminder_actions)
        reminder_layout.addWidget(label("“知道了”仅确认已读，不代表已经起身，也不会重置计时。", role="muted"))
        self._side_panel.hide()
        self._footer = label(role="muted")
        self._quick_links = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self._quick_links.setSpacing(8)
        for title, target in (("今日症状 · 尚未接入记录", "record"), ("我的训练计划", "training")):
            button = self._button(title, lambda key=target: self.show_page(key))
            self._quick_links.addWidget(button)
        self._page_layout.addLayout(self._quick_links)
        self._page_layout.addWidget(self._footer)
        self._page_layout.addStretch()
        self._pages.update(build_pages(
            self,
            symptom_service=self._symptom_service,
            training_service=self._training_service,
            statistics_service=self._statistics_service,
        ))
        for key, content in self._pages.items():
            if key != "home":
                self._body_layout.addWidget(content)
                content.hide()
        self._adapt_layout()

    def _build_sidebar(self, shell_layout):
        self._sidebar = QWidget()
        self._sidebar.setObjectName("sidebar")
        self._sidebar.setFixedWidth(176)
        shell_layout.addWidget(self._sidebar)
        layout = QVBoxLayout(self._sidebar)
        layout.setContentsMargins(12, 24, 12, 16)
        layout.setSpacing(8)
        self._sidebar_brand = Illustration("brand.svg")
        self._sidebar_brand.setFixedSize(48, 48)
        layout.addWidget(self._sidebar_brand, 0, Qt.AlignmentFlag.AlignCenter)
        self._brand_title = label(APP_NAME, role="brand")
        self._brand_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._brand_title)
        layout.addSpacing(24)
        self._nav_buttons = []
        for index, (name, title) in enumerate((
            ("home", "首页"), ("record", "症状记录"), ("training", "康复训练"),
            ("chart", "数据统计"), ("settings", "设置"), ("info", "帮助"),
        )):
            button = QPushButton(title)
            button.setProperty("role", "nav")
            button.setIcon(icon(name, COLORS["primary"] if index == 0 else COLORS["muted"]))
            button.setIconSize(QSize(20, 20))
            button.setMinimumHeight(46)
            button.setAccessibleName(title)
            button.setToolTip(title if index == 0 else f"{title}：可查看页面；未接入业务的操作会明确标注")
            button.setCheckable(True)
            button.setChecked(index == 0)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _checked=False, key=name: self.show_page(key))
            layout.addWidget(button)
            self._nav_buttons.append((button, title))
        self._nav_note = label("页面已补齐\n部分业务待实现", role="muted")
        layout.addWidget(self._nav_note)
        layout.addStretch()
        self._plant = Illustration("plant.svg")
        self._plant.setFixedSize(124, 124)
        layout.addWidget(self._plant, 0, Qt.AlignmentFlag.AlignCenter)
        self._sidebar_quote = label(APP_SLOGAN, role="muted")
        layout.addWidget(self._sidebar_quote)
        self._version = label("V1 · 本地运行", role="muted")
        layout.addWidget(self._version)

    def show_page(self, key):
        if key not in self._pages:
            raise ValueError(f"Unknown page: {key}")
        self._current_page = key
        for name, content in self._pages.items():
            content.setVisible(name == key)
        keys = ("home", "record", "training", "chart", "settings", "info")
        blocked = self._compact_navigation.blockSignals(True)
        self._compact_navigation.setCurrentIndex(keys.index(key))
        self._compact_navigation.blockSignals(blocked)
        for name, (button, _) in zip(keys, self._nav_buttons):
            button.setChecked(name == key)
            button.setIcon(icon(name, COLORS["primary"] if name == key else COLORS["muted"]))
        self._last_layout_key = None
        self._adapt_layout()
        self.centralWidget().verticalScrollBar().setValue(0)
        page = self._pages.get(key)
        if page is not None and hasattr(page, "refresh_history"):
            page.refresh_history()

    def open_page(self, key):
        self.show_page(key)
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _stat_card(self, icon_name, title, value, hint):
        frame = QFrame()
        frame.setProperty("role", "statCard")
        row = QHBoxLayout(frame)
        row.setContentsMargins(16, 18, 16, 18)
        row.setSpacing(14)
        image = QLabel()
        image.setPixmap(icon(icon_name).pixmap(32, 32))
        image.setFixedSize(36, 36)
        row.addWidget(image)
        text = QVBoxLayout()
        text.setSpacing(5)
        text.addWidget(label(title, role="muted"))
        number = label(value, role="metric")
        text.addWidget(number)
        help_text = label(hint, role="muted")
        text.addWidget(help_text)
        row.addLayout(text, 1)
        self._stats_layout.addWidget(frame, 1)
        return number, help_text

    def _adapt_layout(self):
        layout_key = (self.width(), self._rendered_posture, self._rendered_reminders,
                      len(self._elapsed.text()), self._current_page)
        if layout_key == getattr(self, "_last_layout_key", None):
            return
        self._last_layout_key = layout_key
        narrow = self.width() < 900
        compact_nav = self.width() < 700
        # Windows can constrain a high-DPI window below its requested minimum.
        tiny = self.width() < 400
        self._sidebar.setVisible(not tiny)
        self._compact_navigation.setVisible(tiny)
        self._features.adapt(self.width())
        self._quick_links.setDirection(QBoxLayout.Direction.TopToBottom if narrow else QBoxLayout.Direction.LeftToRight)
        for key, content in self._pages.items():
            if key != "home":
                content.adapt(self.width())
        self._content_layout.setDirection(
            QBoxLayout.Direction.TopToBottom if narrow else QBoxLayout.Direction.LeftToRight
        )
        self._stats_layout.setDirection(
            QBoxLayout.Direction.TopToBottom if narrow else QBoxLayout.Direction.LeftToRight
        )
        self._action_layout.setDirection(
            QBoxLayout.Direction.TopToBottom
            if narrow or self._rendered_posture == "NEEDS_CONFIRMATION"
            else QBoxLayout.Direction.LeftToRight
        )
        self._sidebar.setFixedWidth(72 if compact_nav else 176)
        self._brand_title.setVisible(not compact_nav)
        self._nav_note.setVisible(not compact_nav)
        self._plant.setVisible(not compact_nav)
        self._sidebar_quote.setVisible(not compact_nav)
        self._version.setVisible(not compact_nav)
        for index, (button, title) in enumerate(self._nav_buttons):
            button.setText("" if compact_nav else title)
        self._page_layout.setContentsMargins(16 if narrow else 24, 24, 16 if narrow else 24, 20)
        # Budget for side navigation, page/card gutters and a vertical scrollbar.
        available = self.width() - (0 if tiny else 72 if compact_nav else 176) - 96
        diameter = min(300, max(180, available)) if narrow else 300
        if self._track.width() != diameter:
            self._track.setFixedSize(diameter, diameter)
            ratio = diameter / 300
            self._ring_layout.setContentsMargins(round(36 * ratio), round(48 * ratio),
                                                 round(36 * ratio), round(48 * ratio))
            self._posture_art.setFixedSize(round(110 * ratio), round(90 * ratio))
        set_property(self._elapsed, "compact", len(self._elapsed.text()) > 6 or diameter < 260)
        set_property(self._elapsed, "tiny", diameter < 230 or (diameter < 280 and len(self._elapsed.text()) > 6))
        self._content_layout.invalidate()
        self._hero.layout().invalidate()
        self._hero.layout().activate()
        self._page_layout.invalidate()
        self._page_layout.activate()
        self._home_page.updateGeometry()
        self._body_layout.invalidate()
        self._body_layout.activate()
        self._body_layout.parentWidget().updateGeometry()
        # Clear the shell's cached minimum after shrinking the inner ring.
        shell_layout = self.centralWidget().widget().layout()
        shell_layout.invalidate()
        shell_layout.activate()
        # Publish the measured size now. A deferred LayoutRequest otherwise
        # leaves QScrollArea's scrollbar range at the pre-polish width for a
        # full event turn, even though the shell's minimum is already smaller.
        scroll = self.centralWidget()
        shell = scroll.widget()
        width = max(scroll.viewport().width(), shell.minimumSizeHint().width())
        height = shell_layout.totalHeightForWidth(width) if shell_layout.hasHeightForWidth() else shell.minimumSizeHint().height()
        shell.resize(width, max(scroll.viewport().height(), height))

    def _settle_layout(self):
        # A first native show can polish fonts after resizeEvent. Re-measure
        # once on the next event turn, rather than waiting for a timer refresh.
        self._last_layout_key = None
        self._adapt_layout()

    def showEvent(self, event):
        super().showEvent(event)
        self._layout_settler.start(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "_content_layout"):
            self._adapt_layout()
            self._layout_settler.start(0)

    def _refresh_posture(self) -> None:
        self._refresh_statistics()
        self._footer.setText(
            "数据仅保存在本机 · 关闭窗口后仍在托盘运行"
            if self._tray.isVisible() else
            "数据仅保存在本机 · 托盘不可用时，关闭窗口将退出程序"
        )
        if self._posture is None:
            self._summary.setText("追踪未启用")
            self._headline.setText("应用框架已启动")
            self._time_context.setText("坐姿追踪尚未启用")
            self._notice.setText("当前没有可用的坐姿服务，不能开始计时。")
            return
        if self._environment is not None:
            try:
                self._environment.poll_once()
            except Exception:
                logging.getLogger(__name__).exception("Environment polling failed")
                self._show_error("环境信号读取失败；请使用人工确认，详见本机日志。")
        if self._reminders is not None:
            try:
                self._reminders.evaluate_and_deliver()
            except Exception:
                logging.getLogger(__name__).exception("Reminder evaluation failed")
                self._show_error("提醒处理失败，请勿依赖本次自动提醒；详见本机日志。")
        state = self._posture.state
        seconds = self._posture.elapsed_seconds()
        pending = self._reminders.pending_reminders() if self._reminders else ()
        labels = {
            "UNKNOWN": ("尚未确认姿势", "现在正在坐着吗？", "等待你的人工确认", "现在正在坐着吗？请选择下方符合实际情况的操作。", "neutral"),
            "SITTING": ("正在坐着", "留意时间，及时起身", "按人工确认的坐姿开始计时", "可以随时起身，无需等到提醒时间。", "normal"),
            "UP": ("已起身", "本次坐姿已结束", "重新坐下时，再开始新的计时", "已记录你的起身确认，不自动判断何时重新坐下。", "normal"),
            "PAUSED": ("暂停追踪", "按你的节奏恢复", "当前不进行坐姿计时", "追踪已暂停。恢复时需要重新确认姿势。", "neutral"),
            "NEEDS_CONFIRMATION": ("中断后待核实", "先核实这段时间", "有未核实区间，不显示确定时长", "发生中断，不能确定期间的真实姿势。请按实际情况核实。", "warning"),
        }
        status, headline, context, notice, tone = labels[state.posture]
        if state.posture == "SITTING":
            if seconds is not None and seconds >= 2400:
                headline, notice, tone = "已达上限，请及时起身", "已达到 40 分钟上限。确认起身前，计时与警示会保留。", "danger"
            elif seconds is not None and seconds >= 2100:
                headline, notice, tone = "该给坐姿一个间歇了", "已到 35 分钟提醒时间，建议起身。", "warning"
            if state.uncertain:
                context = "按上次确认推算，可能不准确"
                notice = context + "。" + notice
        self._summary.setText(status)
        self._headline.setText(headline)
        self._time_context.setText(context)
        self._timer_caption.setText("本次坐姿 · 推算时间" if state.uncertain else "本次坐姿 · 经过时间")
        self._elapsed.setText(f"{seconds // 60:02d}:{seconds % 60:02d}" if seconds is not None else "--:--")
        self._elapsed.setAccessibleName(
            f"本次坐姿{'推算' if state.uncertain else '经过'}时间 {seconds // 60} 分 {seconds % 60} 秒"
            if seconds is not None else "暂无已确认的坐姿计时"
        )
        self._track.set_seconds(seconds, state.uncertain)
        self._posture_art.set_asset("sitting.svg" if state.posture == "SITTING" else "brand.svg")
        self._refresh_time_details(state, seconds)
        self._notice.setText(notice)
        set_property(self._summary, "tone", tone)
        set_property(self._status_dot, "tone", tone)
        set_property(self._notice, "tone", tone)
        if self._rendered_posture != state.posture:
            self._rendered_posture = state.posture
            self._build_actions(state.posture)
        reminder_key = tuple(item.id for item in pending)
        if self._rendered_reminders != reminder_key:
            self._rendered_reminders = reminder_key
            self._build_reminders(pending)
        if self._action_layout.count():
            set_property(self._action_layout.itemAt(0).widget(), "tone", tone)
        self._adapt_layout()

    def _refresh_statistics(self):
        if self._statistics_service is None:
            return
        try:
            row = self._statistics_service.recent(7)[-1]
        except Exception:
            logging.getLogger(__name__).exception("Could not refresh home statistics")
            self._today_time.setText("—")
            self._today_time_hint.setText("统计读取失败")
            self._today_up.setText("—")
            self._today_up_hint.setText("统计读取失败")
            return

        if row.sitting_seconds is None:
            self._today_time.setText("—")
            self._today_time_hint.setText("暂无已闭合记录")
        else:
            minutes = row.sitting_seconds // 60
            hours, remainder = divmod(minutes, 60)
            value = f"{hours} 小时 {remainder} 分" if hours else f"{remainder} 分"
            self._today_time.setText(value)
            self._today_time_hint.setText("已确认坐姿时长")

        if row.up_count is None:
            self._today_up.setText("—")
            self._today_up_hint.setText("暂无人工确认记录")
        else:
            self._today_up.setText(f"{row.up_count} 次")
            self._today_up_hint.setText("人工确认起身次数")

    def _refresh_time_details(self, state, seconds):
        if state.sitting_since:
            try:
                started = datetime.fromisoformat(state.sitting_since).astimezone()
                prefix = "上次坐姿确认于" if state.uncertain or state.posture == "NEEDS_CONFIRMATION" else "本次坐姿开始于"
                self._started_at.setText(f"{prefix} {started:%Y-%m-%d %H:%M}")
            except (ValueError, OverflowError):
                self._started_at.setText("坐姿开始时间不可用，请核对记录")
        else:
            self._started_at.setText("尚无已确认的坐姿开始时间")
        if seconds is None:
            self._countdown.setText("等待核实" if state.posture == "NEEDS_CONFIRMATION" else "暂无坐姿计时")
            self._next_value.setText("等待核实" if state.posture == "NEEDS_CONFIRMATION" else "等待确认")
            self._next_hint.setText("确认坐姿后开始提醒" if state.posture != "PAUSED" else "追踪已暂停")
            return
        # Mirrors the frozen V1 thresholds, not notification delivery or read status.
        next_minute = next((minute for minute in (35, 40, 45, 50, 55) if seconds < minute * 60), None)
        estimated = "推算 · " if state.uncertain else ""
        if next_minute is None:
            self._next_value.setText("已达提醒上限")
            self._next_hint.setText("无后续定时提醒；起身前保留警示")
        else:
            remaining = next_minute * 60 - seconds
            countdown = f"{remaining // 60}:{remaining % 60:02d}"
            self._next_value.setText(countdown)
            self._next_hint.setText(estimated + (f"{next_minute} 分钟" if next_minute <= 40 else "上限后的有限重复提醒"))
        self._countdown.setText(
            estimated + f"距 {next_minute} 分钟还有 {countdown}" if seconds < 2400 else
            estimated + "已达 40 分钟上限"
        )

    def _button(self, text, callback, *, primary=False):
        button = QPushButton(text)
        button.setMinimumHeight(46)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setAccessibleName(text)
        button.setIcon(icon("up" if "起身" in text else "pause" if "暂停" in text else "check",
                            "#FFFFFF" if primary else COLORS["muted"]))
        button.setIconSize(QSize(20, 20))
        button.setProperty("role", "primary" if primary else "secondary")
        button.clicked.connect(lambda _checked=False: callback())
        return button

    def _build_actions(self, posture):
        focused = self.focusWidget()
        had_focus = focused is not None and self._actions.isAncestorOf(focused)
        clear_layout(self._action_layout)
        actions = {
            "UNKNOWN": (("现在坐着", self._posture.confirm_sitting), ("现在已起身", self._posture.confirm_up)),
            "SITTING": (("我已起身", self._posture.confirm_up), ("暂停追踪", self._posture.pause)),
            "UP": (("重新坐下", self._posture.confirm_sitting), ("暂停追踪", self._posture.pause)),
            "PAUSED": (("恢复并重新确认", self._posture.resume_needs_confirmation),),
            "NEEDS_CONFIRMATION": (
                ("一直坐着（自述）", self._posture.reconcile_continue_sitting),
                ("现在已起身", self._posture.confirm_up),
                ("无法确认", self._posture.reconcile_unknown),
            ),
        }
        for index, (text, callback) in enumerate(actions[posture]):
            button = self._button(text, lambda fn=callback: self._run_posture_action(fn), primary=index == 0)
            self._action_layout.addWidget(button)
        self._update_tab_order()
        if had_focus:
            self._action_layout.itemAt(0).widget().setFocus(Qt.FocusReason.OtherFocusReason)

    def _build_reminders(self, pending):
        focused = self.focusWidget()
        had_focus = focused is not None and self._reminder_actions.isAncestorOf(focused)
        clear_layout(self._reminder_layout)
        self._reminder_count.setText(f"{len(pending)} 条")
        self._side_panel.setVisible(bool(pending))
        self._reminder_empty.setVisible(not pending)
        self._reminder_actions.setVisible(bool(pending))
        for reminder in pending:
            row = QWidget()
            layout = QHBoxLayout(row)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(10)
            text = (
                f"上限后第 {reminder.sequence_no} 次提醒" if reminder.sequence_no else
                f"{reminder.threshold_minutes} 分钟{'上限' if reminder.threshold_minutes == 40 else '提醒'}"
            )
            layout.addWidget(label(text, role="muted"), 1)
            button = self._button("知道了", lambda rid=reminder.id: self._acknowledge_reminder(rid))
            button.setAccessibleName(f"知道了，{text}；仅确认已读")
            button.setToolTip("仅确认已读，不代表起身，也不会清零坐姿计时")
            layout.addWidget(button)
            self._reminder_layout.addWidget(row)
        self._update_tab_order()
        if had_focus:
            buttons = self._reminder_actions.findChildren(QPushButton)
            visible_buttons = [button for button in buttons if not button.isHidden() and not button.parentWidget().isHidden()]
            target = visible_buttons[0] if visible_buttons else self._action_layout.itemAt(0).widget()
            target.setFocus(Qt.FocusReason.OtherFocusReason)

    def _update_tab_order(self):
        buttons = [self._action_layout.itemAt(i).widget() for i in range(self._action_layout.count())]
        for i in range(self._reminder_layout.count()):
            buttons.extend(self._reminder_layout.itemAt(i).widget().findChildren(QPushButton))
        for first, second in zip(buttons, buttons[1:]):
            self.setTabOrder(first, second)

    def _show_error(self, text):
        self._error_message.setText(text)
        self._error_message.show()

    def _run_posture_action(self, callback) -> None:
        try:
            callback()
            self._error_message.hide()
        except Exception:
            logging.getLogger(__name__).exception("Posture action failed")
            self._show_error("操作未完成，请核对当前状态后重试；详见本机日志。")
        self._refresh_posture()

    def _acknowledge_reminder(self, delivery_id: int) -> None:
        if self._reminders is None:
            return
        try:
            self._reminders.acknowledge_seen(delivery_id)
            self._error_message.hide()
        except Exception:
            logging.getLogger(__name__).exception("Reminder acknowledgement failed")
            self._show_error("已读确认未完成，请重试。详见本机日志。")
        self._refresh_posture()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._allow_exit or not self._tray.isVisible():
            self._refresh_timer.stop()
            event.accept()
        else:
            event.ignore()
            self.hide()
