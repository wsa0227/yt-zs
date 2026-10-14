"""Design-board page skeletons. No health persistence or training execution here."""
import logging
from datetime import date

from PySide6.QtCore import QDate, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QAbstractItemView, QBoxLayout, QCheckBox, QComboBox, QDateEdit, QDialog,
    QDialogButtonBox, QFileDialog, QGridLayout, QHeaderView, QHBoxLayout, QInputDialog,
    QLayout, QLineEdit, QMessageBox,
    QPushButton, QSizePolicy, QSlider, QTableWidget, QTableWidgetItem,
    QTabWidget, QTextEdit, QToolButton, QVBoxLayout, QWidget,
)
from rehab_assistant import APP_NAME
from rehab_assistant.domain.exercises import ExerciseRecord, SYMPTOM_CHANGES
from rehab_assistant.domain.symptoms import SymptomRecord
from rehab_assistant.domain.statistics import DailyStatistics
from rehab_assistant.safety.symptom_rules import evaluate_symptoms
from .components import card, label
from .theme import COLORS
from .widgets import Illustration, icon


CAPABILITIES = (
    ("shield", "本地运行", "保护隐私", "settings"),
    ("monitor", "开机常驻", "系统托盘", "settings"),
    ("bell", "定时提醒", "35/40分钟", "settings"),
    ("chart", "记录趋势", "了解变化", "chart"),
    ("training", "康复训练", "专业指导", "training"),
)


class FeatureStrip(QWidget):
    def __init__(self, navigate):
        super().__init__()
        self.setObjectName("featureStrip")
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(10)
        self.buttons = []
        for name, title, subtitle, target in CAPABILITIES:
            button = QToolButton()
            button.setProperty("role", "capability")
            button.setText(f"{title}\n{subtitle}")
            button.setAccessibleName(f"{title}，{subtitle}；打开相关页面查看实现状态")
            button.setToolTip("能力入口不代表全部业务已完成；详情见相关页面")
            button.setIcon(icon(name))
            button.setIconSize(QSize(28, 28))
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            button.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            button.setMinimumHeight(106)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _checked=False, key=target: navigate(key))
            self.buttons.append(button)
        self._columns = None
        self.adapt(1040)

    def adapt(self, width):
        columns = 5 if width >= 900 else 3 if width >= 600 else 2
        if columns == self._columns:
            return
        self._columns = columns
        while self.grid.count():
            self.grid.takeAt(0)
        for column in range(5):
            self.grid.setColumnStretch(column, 1 if column < columns else 0)
        for index, button in enumerate(self.buttons):
            self.grid.addWidget(button, index // columns, index % columns)


class DesignPage(QWidget):
    def __init__(self, title, subtitle, phase):
        super().__init__()
        self.setObjectName("designPage")
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(24, 24, 24, 20)
        self.body.setSpacing(16)
        self.body.addWidget(label(title, role="title"))
        self.body.addWidget(label(subtitle, role="muted"))
        self.status = label(f"界面已搭建 · {phase}业务待实现", role="stage")
        self.body.addWidget(self.status)
        self.rows = []
        self._adapt_callbacks = []

    def section(self, title):
        frame, layout = card()
        layout.addWidget(label(title, role="section"))
        self.body.addWidget(frame)
        return layout

    def row(self, layout):
        row = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        row.setSpacing(12)
        layout.addLayout(row)
        self.rows.append(row)
        return row

    def add_adapt_callback(self, callback):
        """Register page-specific responsive layout work."""
        self._adapt_callbacks.append(callback)

    def adapt(self, width):
        narrow = width < 900
        self.body.setContentsMargins(16 if narrow else 24, 24, 16 if narrow else 24, 20)
        for row in self.rows:
            row.setDirection(QBoxLayout.Direction.TopToBottom if narrow else QBoxLayout.Direction.LeftToRight)
        for callback in self._adapt_callbacks:
            callback(width)
        # Cards/tab pages may cache a wide row's minimum even after it stacks.
        # Invalidate inside-out before the scroll container measures this page.
        for layout in reversed(self.findChildren(QLayout)):
            layout.invalidate()
            layout.activate()
        self.body.invalidate()
        self.body.activate()

    def finish(self, footer="数据保留在本机 · 页面占位不生成健康记录，也不安排训练"):
        self.body.addWidget(label(footer, role="muted"))
        self.body.addStretch()


class StatisticsChart(QWidget):
    """Small native Qt chart that preserves gaps instead of drawing fake zeroes."""

    def __init__(self, mode: str, parent=None):
        super().__init__(parent)
        self.mode = mode
        self._rows: tuple[DailyStatistics, ...] = ()
        self.setMinimumHeight(220)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setAccessibleName("统计趋势图")

    def set_rows(self, rows: tuple[DailyStatistics, ...]) -> None:
        self._rows = rows
        self.setToolTip(self._tooltip_text())
        self.update()

    def sizeHint(self):
        return QSize(640, 220)

    def _value(self, row: DailyStatistics) -> float | None:
        if self.mode == "sitting":
            return None if row.sitting_seconds is None else row.sitting_seconds / 60
        if self.mode == "symptoms":
            return None if not row.symptom_recorded or row.pain_score is None else float(row.pain_score)
        return None if row.up_count is None else float(row.up_count)

    def _unit(self) -> str:
        return {"sitting": "分钟", "symptoms": "分", "up": "次"}[self.mode]

    def _tooltip_text(self) -> str:
        if not self._rows:
            return "暂无统计数据"
        entries = []
        for row in self._rows:
            value = self._value(row)
            entries.append(f"{row.record_date_local}：{value:g} {self._unit()}" if value is not None
                           else f"{row.record_date_local}：暂无记录")
        return "\n".join(entries)

    def paintEvent(self, event):  # noqa: N802 - Qt API name
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(COLORS["surface"]))
        left, top, right, bottom = 48, 18, 18, 36
        plot = self.rect().adjusted(left, top, -right, -bottom)
        if plot.width() <= 0 or plot.height() <= 0:
            return

        painter.setPen(QPen(QColor(COLORS["border"]), 1))
        painter.drawLine(plot.left(), plot.bottom(), plot.right(), plot.bottom())
        painter.drawLine(plot.left(), plot.top(), plot.left(), plot.bottom())
        if not self._rows:
            self._draw_centered(painter, plot, "暂无记录")
            return

        values = [self._value(row) for row in self._rows]
        present = [value for value in values if value is not None]
        if not present:
            self._draw_centered(painter, plot, "暂无已确认记录")
            return
        maximum = max(present)
        if self.mode == "symptoms":
            maximum = 10
        else:
            maximum = max(1.0, maximum)
        color = QColor(COLORS["green"] if self.mode == "sitting" else COLORS["primary"])
        if self.mode == "symptoms":
            color = QColor(COLORS["warning"])

        count = len(self._rows)
        step = plot.width() / max(1, count)
        points: list[tuple[float, float] | None] = []
        for index, value in enumerate(values):
            x = plot.left() + step * (index + 0.5)
            if value is None:
                points.append(None)
                continue
            y = plot.bottom() - (value / maximum) * plot.height()
            points.append((x, y))
            if self.mode in ("sitting", "up"):
                bar_width = max(8.0, min(30.0, step * 0.46))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(color)
                painter.drawRoundedRect(
                    int(x - bar_width / 2), int(y), int(bar_width),
                    max(2, int(plot.bottom() - y)), 4, 4,
                )

        if self.mode == "symptoms":
            painter.setPen(QPen(color, 2))
            previous = None
            for point in points:
                if point is None:
                    previous = None
                    continue
                if previous is not None:
                    painter.drawLine(int(previous[0]), int(previous[1]), int(point[0]), int(point[1]))
                painter.setBrush(color)
                painter.drawEllipse(int(point[0] - 4), int(point[1] - 4), 8, 8)
                previous = point

        painter.setPen(QColor(COLORS["muted"]))
        painter.setFont(self.font())
        label_step = max(1, count // 6)
        for index, row in enumerate(self._rows):
            if index % label_step != 0 and index != count - 1:
                continue
            x = plot.left() + step * (index + 0.5)
            painter.drawText(int(x - 32), plot.bottom() + 10, 64, 22,
                             Qt.AlignmentFlag.AlignHCenter, row.record_date_local[5:])
        painter.drawText(0, plot.top() - 2, left - 8, 20, Qt.AlignmentFlag.AlignRight,
                         self._axis_maximum(maximum))
        painter.drawText(0, plot.bottom() - 10, left - 8, 20, Qt.AlignmentFlag.AlignRight, "0")

    @staticmethod
    def _axis_maximum(value: float) -> str:
        return f"{value:g}"

    @staticmethod
    def _draw_centered(painter: QPainter, plot, text: str) -> None:
        painter.setPen(QColor(COLORS["muted"]))
        painter.drawText(plot, Qt.AlignmentFlag.AlignCenter, text)


def pending_button(text, parent_layout, reason="业务尚未接入，本轮不能执行此操作"):
    button = QPushButton(text)
    button.setMinimumHeight(44)
    # Let stacked narrow layouts determine the button width instead of making
    # the page's minimum width equal to the longest placeholder label.
    button.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
    button.setEnabled(False)
    button.setToolTip(reason)
    button.setAccessibleName(f"{text}，待实现：{reason}")
    parent_layout.addWidget(button)
    return button


def tabs(layout, titles):
    widget = QTabWidget()
    widget.setDocumentMode(True)
    widget.setUsesScrollButtons(True)
    widget.tabBar().setElideMode(Qt.TextElideMode.ElideRight)
    widget.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
    result = []
    for title in titles:
        page = QWidget()
        body = QVBoxLayout(page)
        body.setContentsMargins(12, 20, 12, 12)
        body.setSpacing(16)
        widget.addTab(page, title)
        result.append(body)
    layout.addWidget(widget)
    return widget, result


def symptoms_page(symptom_service=None):
    page = DesignPage("症状记录", "记录今天的身体状况；每日记录可跳过，不影响坐姿提醒。", "Phase 4A：症状记录与安全提示，")
    form = page.section("记录今天的身体状况")
    page.current_record_id = None
    page._symptom_service = symptom_service
    form.addWidget(label(
        "记录保存在本机；疼痛评分可跳过，未填写与 0 分是不同状态。"
        if symptom_service else
        "表单仅在当前窗口内编辑；尚未接入保存、编辑或删除，关闭后不会保留。",
        role="muted",
    ))
    form.addWidget(label("记录日期（本地）", role="field"))
    page.record_date = QDateEdit(date.today())
    page.record_date.setCalendarPopup(True)
    page.record_date.setDisplayFormat("yyyy-MM-dd")
    page.record_date.setAccessibleName("记录日期")
    form.addWidget(page.record_date)
    page.score_label = label("疼痛评分 · 未填写（可跳过）", role="field")
    form.addWidget(page.score_label)
    page.score = QSlider(Qt.Orientation.Horizontal)
    page.score.setRange(0, 10)
    page.score.setTickPosition(QSlider.TickPosition.TicksBelow)
    page.score.setTickInterval(1)
    page.score.setMinimumHeight(44)
    page.score.setAccessibleName("疼痛评分，0至10；默认未填写")
    page.score_unset = True

    def score_changed(value):
        page.score_unset = False
        page.score_label.setText(f"疼痛评分 · {value} / 10（未保存）")

    page.score.valueChanged.connect(score_changed)
    form.addWidget(page.score)
    score_row = page.row(form)
    choose_zero = QPushButton("选择 0 分")
    choose_zero.setMinimumHeight(44)

    def choose_zero_score():
        page.score_unset = False
        if page.score.value() == 0:
            page.score_label.setText("疼痛评分 · 0 / 10（未保存）")
        else:
            page.score.setValue(0)

    choose_zero.clicked.connect(choose_zero_score)
    score_row.addWidget(choose_zero)
    skip = QPushButton("跳过评分")
    skip.setMinimumHeight(44)
    def skip_score():
        blocked = page.score.blockSignals(True)
        page.score.setValue(0)
        page.score.blockSignals(blocked)
        page.score_unset = True
        page.score_label.setText("疼痛评分 · 未填写（可跳过）")
    skip.clicked.connect(skip_score)
    score_row.addWidget(skip)
    form.addWidget(label("疼痛部位（可多选）", role="field"))
    body_grid = QGridLayout()
    page.body_checks = []
    for index, text in enumerate(("下腰部", "左背部", "右背部", "左腿", "右腿", "其他")):
        check = QCheckBox(text)
        check.setMinimumHeight(44)
        body_grid.addWidget(check, index // 2, index % 2)
        page.body_checks.append(check)
    form.addLayout(body_grid)
    form.addWidget(label("是否新增腿部症状", role="field"))
    page.leg_symptoms = QComboBox()
    page.leg_symptoms.addItems(("未填写", "无新增症状", "新增腿痛", "新增麻木", "新增无力", "多种症状"))
    page.leg_symptoms.setAccessibleName("是否新增腿部症状")
    form.addWidget(page.leg_symptoms)
    form.addWidget(label("与活动关系", role="field"))
    page.activity_relation = QComboBox()
    page.activity_relation.addItems(("未知", "坐姿时", "站姿时", "弯腰时", "其他"))
    page.activity_relation.setAccessibleName("与活动关系")
    form.addWidget(page.activity_relation)
    form.addWidget(label("需要优先就医评估的警示信号（如有请勾选）", role="field"))
    safety_grid = QGridLayout()
    page.safety_checks = {}
    for index, (flag, text) in enumerate((
        ("perineal_numbness", "会阴 / 肛周麻木"),
        ("urinary_retention", "无法排尿"),
        ("bowel_bladder_change", "排尿或排便控制改变"),
        ("exercise_worsening", "训练后症状明显加重 / 放射"),
    )):
        check = QCheckBox(text)
        check.setMinimumHeight(44)
        check.setAccessibleName(text)
        safety_grid.addWidget(check, index // 2, index % 2)
        page.safety_checks[flag] = check
    form.addLayout(safety_grid)

    def adapt_symptom_grids(width):
        # Keep the two-column form on normal desktop widths, but stack labels
        # whose text is too long to share a narrow column. This prevents the
        # safety section from exporting a wider minimum than the window.
        columns = 1 if width < 600 else 2
        for grid, widgets in ((body_grid, page.body_checks), (safety_grid, tuple(page.safety_checks.values()))):
            for index, widget in enumerate(widgets):
                grid.addWidget(widget, index // columns, index % columns)
            for column in range(2):
                grid.setColumnStretch(column, 1 if column < columns else 0)

    page.add_adapt_callback(adapt_symptom_grids)
    for title, choices in ():
        form.addWidget(label(title, role="field"))
        combo = QComboBox()
        combo.addItems(choices)
        combo.setAccessibleName(title)
        form.addWidget(combo)
    form.addWidget(label("其他症状 / 备注（可选）", role="field"))
    page.notes = QTextEdit()
    page.notes.setPlaceholderText("请简单描述今天的身体状况…")
    page.notes.setAccessibleName("其他症状和备注")
    page.notes.setFixedHeight(100)
    form.addWidget(page.notes)
    page.feedback = label("", role="muted")
    page.feedback.setWordWrap(True)
    page.feedback.hide()
    form.addWidget(page.feedback)
    page.save_button = QPushButton("保存记录" if symptom_service else "保存记录 · 待实现")
    page.save_button.setMinimumHeight(44)
    page.save_button.setEnabled(symptom_service is not None)
    page.save_button.setToolTip("保存当天记录；同一天再次保存会更新原记录。" if symptom_service else "业务尚未接入，本轮不能执行此操作")
    form.addWidget(page.save_button)
    records = page.section("历史记录")
    page.history_status = label(
        "历史记录尚未接入 · 此处不代表你没有症状记录" if symptom_service is None else "",
        role="muted",
    )
    records.addWidget(page.history_status)
    page.history_table = QTableWidget(0, 7)
    page.history_table.setHorizontalHeaderLabels(("日期", "评分", "部位", "腿部症状", "活动关系", "警示", "备注"))
    page.history_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    page.history_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    page.history_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    page.history_table.setMinimumHeight(180)
    page.history_table.setMinimumWidth(0)
    page.history_table.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
    page.history_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    page.history_table.setWordWrap(True)
    page.history_table.setAccessibleName("症状历史记录")
    page.history_table.horizontalHeader().setMinimumSectionSize(32)
    page.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    page.history_table.itemSelectionChanged.connect(lambda: update_history_actions())
    records.addWidget(page.history_table)
    row = page.row(records)
    page.edit_button = QPushButton("编辑记录" if symptom_service else "编辑 / 删除 · 待实现")
    page.edit_button.setMinimumHeight(44)
    page.edit_button.setEnabled(False if symptom_service else False)
    page.edit_button.setToolTip("先选择一条历史记录" if symptom_service else "业务尚未接入，本轮不能执行此操作")
    row.addWidget(page.edit_button)
    page.delete_button = QPushButton("删除记录" if symptom_service else "编辑 / 删除 · 待实现")
    page.delete_button.setMinimumHeight(44)
    page.delete_button.setEnabled(False if symptom_service else False)
    page.delete_button.setToolTip("删除前会要求确认" if symptom_service else "业务尚未接入，本轮不能执行此操作")
    row.addWidget(page.delete_button)
    page.export_button = QPushButton("导出 CSV" if symptom_service else "导出 CSV · 待实现")
    page.export_button.setMinimumHeight(44)
    page.export_button.setEnabled(symptom_service is not None)
    page.export_button.setToolTip("导出本机症状记录，不含身份标识。" if symptom_service else "业务尚未接入，本轮不能执行此操作")
    row.addWidget(page.export_button)

    def show_feedback(text, tone="muted"):
        page.feedback.setText(text)
        page.feedback.setProperty("tone", tone)
        page.feedback.show()
        page.feedback.style().unpolish(page.feedback)
        page.feedback.style().polish(page.feedback)

    def read_form():
        return SymptomRecord(
            id=page.current_record_id,
            record_date_local=page.record_date.date().toString("yyyy-MM-dd"),
            pain_score=None if page.score_unset else page.score.value(),
            body_locations=tuple(check.text() for check in page.body_checks if check.isChecked()),
            leg_symptoms=page.leg_symptoms.currentText(),
            activity_relation=page.activity_relation.currentText(),
            safety_flags=tuple(flag for flag, check in page.safety_checks.items() if check.isChecked()),
            notes=page.notes.toPlainText(),
            created_at_utc=None,
            updated_at_utc=None,
        )

    def refresh_history():
        if symptom_service is None:
            return
        try:
            entries = symptom_service.list_records()
        except Exception:
            logging.getLogger(__name__).exception("Could not load symptom history")
            show_feedback("历史记录读取失败，请重试；详见本机日志。", "danger")
            return
        page.history_table.setRowCount(0)
        for entry in entries:
            row_index = page.history_table.rowCount()
            page.history_table.insertRow(row_index)
            alerts = evaluate_symptoms(entry)
            values = (
                entry.record_date_local,
                "未填写" if entry.pain_score is None else str(entry.pain_score),
                "、".join(entry.body_locations) or "未填写",
                entry.leg_symptoms,
                entry.activity_relation,
                "；".join(alert.code for alert in alerts) or "无",
                entry.notes,
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, entry.id)
                page.history_table.setItem(row_index, column, item)
        page.history_status.setText("暂无已保存的症状记录" if not entries else f"共 {len(entries)} 条记录；缺失日期不会补为 0")
        update_history_actions()

    def selected_id():
        selected = page.history_table.selectedItems()
        return int(selected[0].data(Qt.ItemDataRole.UserRole)) if selected else None

    def update_history_actions():
        has_selection = selected_id() is not None
        page.edit_button.setEnabled(symptom_service is not None and has_selection)
        page.delete_button.setEnabled(symptom_service is not None and has_selection)

    def load_record(entry):
        page.current_record_id = entry.id
        page.record_date.setDate(QDate.fromString(entry.record_date_local, "yyyy-MM-dd"))
        page.score_unset = entry.pain_score is None
        blocked = page.score.blockSignals(True)
        page.score.setValue(entry.pain_score or 0)
        page.score.blockSignals(blocked)
        page.score_label.setText(
            "疼痛评分 · 未填写（可跳过）" if page.score_unset else f"疼痛评分 · {entry.pain_score} / 10（已保存）"
        )
        for check in page.body_checks:
            check.setChecked(check.text() in entry.body_locations)
        page.leg_symptoms.setCurrentText(entry.leg_symptoms)
        page.activity_relation.setCurrentText(entry.activity_relation)
        for flag, check in page.safety_checks.items():
            check.setChecked(flag in entry.safety_flags)
        page.notes.setPlainText(entry.notes)
        show_feedback(f"已载入 {entry.record_date_local}，修改后点击保存记录。")

    def save_record():
        try:
            saved = symptom_service.save(read_form())
        except Exception:
            logging.getLogger(__name__).exception("Symptom record save failed")
            show_feedback("保存失败，未显示成功状态；请检查输入后重试。", "danger")
            return
        page.current_record_id = saved.id
        refresh_history()
        alerts = evaluate_symptoms(saved)
        if alerts:
            show_feedback("记录已保存。\n" + "\n".join(alert.message for alert in alerts), "danger")
        else:
            show_feedback(f"已保存 {saved.record_date_local} 的本地症状记录。", "success")

    def edit_record():
        record_id = selected_id()
        if record_id is None:
            return
        entry = symptom_service.get_by_id(record_id)
        if entry is not None:
            load_record(entry)

    def delete_record():
        record_id = selected_id()
        if record_id is None:
            return
        answer = QMessageBox.question(
            page, "删除症状记录", "确认删除选中的本地症状记录吗？此操作不可撤销。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            symptom_service.delete(record_id)
        except Exception:
            logging.getLogger(__name__).exception("Symptom record delete failed")
            show_feedback("删除失败，记录未改变；详见本机日志。", "danger")
            return
        if page.current_record_id == record_id:
            page.current_record_id = None
        refresh_history()
        show_feedback("已删除选中的本地症状记录。", "success")

    def export_records():
        path, _ = QFileDialog.getSaveFileName(page, "导出症状记录", "symptoms.csv", "CSV 文件 (*.csv)")
        if not path:
            return
        answer = QMessageBox.question(
            page, "确认导出", "导出的 CSV 可能包含敏感健康信息，仅保存到你选择的位置。继续吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            count = symptom_service.export_csv(path)
        except Exception:
            logging.getLogger(__name__).exception("Symptom CSV export failed")
            show_feedback("导出失败，未生成成功提示；详见本机日志。", "danger")
            return
        show_feedback(f"已导出 {count} 条本地症状记录。", "success")

    page.refresh_history = refresh_history
    page.save_button.clicked.connect(save_record) if symptom_service else None
    page.edit_button.clicked.connect(edit_record) if symptom_service else None
    page.delete_button.clicked.connect(delete_record) if symptom_service else None
    page.export_button.clicked.connect(export_records) if symptom_service else None
    refresh_history()
    page.finish()
    return page


def _exercise_editor(parent):
    dialog = QDialog(parent)
    dialog.setWindowTitle("添加训练资料候选")
    dialog.setMinimumWidth(520)
    body = QVBoxLayout(dialog)
    body.setContentsMargins(24, 24, 24, 24)
    body.setSpacing(12)
    body.addWidget(label("只录入你已有的专业资料；程序不会替你判断动作是否适合。", role="muted"))

    fields = {}
    for key, title, placeholder in (
        ("name", "资料名称", "例如：医生提供的动作资料"),
        ("source_org", "来源机构 / 提供者", "请填写资料来源"),
        ("source_url", "视频 / 图文链接（可选）", "可留空，链接不会被程序验证"),
    ):
        body.addWidget(label(title, role="field"))
        field = QLineEdit()
        field.setPlaceholderText(placeholder)
        field.setAccessibleName(title)
        fields[key] = field
        body.addWidget(field)
    body.addWidget(label("动作内容 / 执行说明", role="field"))
    content = QTextEdit()
    content.setPlaceholderText("粘贴或整理专业人员提供的图文、视频说明")
    fields["content"] = content
    body.addWidget(content)
    body.addWidget(label("禁忌与注意事项", role="field"))
    cautions = QTextEdit()
    cautions.setPlaceholderText("例如：出现不适立即停止，并联系专业人员")
    fields["contraindication_notes"] = cautions
    body.addWidget(cautions)
    error = label(role="errorMessage")
    error.hide()
    body.addWidget(error)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    body.addWidget(buttons)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    values = {key: widget.toPlainText() if isinstance(widget, QTextEdit) else widget.text()
              for key, widget in fields.items()}
    values.update({"id": None, "reviewer": None, "approved_at_utc": None,
                   "status": "CANDIDATE", "created_at_utc": None, "updated_at_utc": None})
    return ExerciseRecord(**values)


def _training_log_editor(parent):
    dialog = QDialog(parent)
    dialog.setWindowTitle("记录训练结果")
    dialog.setMinimumWidth(500)
    body = QVBoxLayout(dialog)
    body.setContentsMargins(24, 24, 24, 24)
    body.setSpacing(12)
    completed = QCheckBox("本次完成")
    completed.setChecked(True)
    body.addWidget(completed)
    body.addWidget(label("本次感受", role="field"))
    response = QTextEdit()
    response.setPlaceholderText("如出现不适，请写明并立即停止相关训练")
    body.addWidget(response)
    body.addWidget(label("症状变化", role="field"))
    change = QComboBox()
    change.addItems(SYMPTOM_CHANGES)
    body.addWidget(change)
    body.addWidget(label("备注", role="field"))
    notes = QTextEdit()
    notes.setPlaceholderText("可选")
    body.addWidget(notes)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    body.addWidget(buttons)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return None
    return {
        "completed": completed.isChecked(), "user_response": response.toPlainText().strip(),
        "symptom_change": change.currentText(), "notes": notes.toPlainText(),
    }


def training_page(training_service=None):
    page = DesignPage("康复训练", "资料候选与执行计划分开；未经专业确认，不安排训练。", "Phase 4B：训练库与计划，")
    page.tab_widget, (library, plan) = tabs(page.body, ("康复动作", "我的计划"))
    library.addWidget(label(
        "专业确认状态由用户手动录入，程序无法验证。设计稿示例动作仍是占位，不是训练建议。",
        role="muted",
    ))
    add_button = QPushButton("添加资料候选")
    add_button.setMinimumHeight(44)
    add_button.setEnabled(training_service is not None)
    add_button.setToolTip("录入已有的专业资料；不会自动推荐或排程")
    library.addWidget(add_button)
    library_dynamic = QVBoxLayout()
    library_dynamic.setSpacing(12)
    library.addLayout(library_dynamic)

    plan_dynamic = QVBoxLayout()
    plan_dynamic.setSpacing(12)
    plan.addLayout(plan_dynamic)
    page._training_service = training_service

    def clear_dynamic(layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def show_error(message):
        QMessageBox.warning(page, "未保存", message)

    def refresh():
        clear_dynamic(library_dynamic)
        clear_dynamic(plan_dynamic)
        if training_service is None:
            for name in ("猫牛式", "桥式", "腰部拉伸"):
                frame, body = card()
                row = page.row(body)
                image = label("动作插图\n待提供", role="artPlaceholder")
                image.setAlignment(Qt.AlignmentFlag.AlignCenter)
                row.addWidget(image)
                detail = QVBoxLayout()
                detail.addWidget(label(f"{name}（设计占位）", role="section"))
                detail.addWidget(label("来源 / 图文 / 注意事项 / 专业确认信息尚未接入", role="muted"))
                detail.addWidget(label("待专业确认 · 不可执行", role="stage"))
                row.addLayout(detail, 1)
                library_dynamic.addWidget(frame)
            library_dynamic.addWidget(label(
                "初始可执行训练为空；这里的占位动作不进入执行计划。", role="muted"
            ))
            empty, body = card()
            body.addWidget(label("尚无可执行训练计划", role="section"))
            body.addWidget(label("计划服务尚未接入；当前页面不会执行训练。", role="muted"))
            plan_dynamic.addWidget(empty)
            return

        records = training_service.list_exercises()
        if not records:
            library_dynamic.addWidget(label("尚无已录入的训练资料候选", role="section"))
            library_dynamic.addWidget(label(
                "请先向专业人员取得资料，再在此录入。初始执行计划为空。", role="muted"
            ))
        for record in records:
            frame, body = card()
            body.addWidget(label(record.name, role="section"))
            body.addWidget(label(f"来源：{record.source_org}" + (f" · {record.source_url}" if record.source_url else ""), role="muted"))
            body.addWidget(label(record.content, role="muted"))
            body.addWidget(label(f"注意事项：{record.contraindication_notes or '未填写'}", role="muted"))
            status_text = {"CANDIDATE": "待专业确认 · 不可执行", "APPROVED": "已录入专业确认 · 可加入计划", "SUSPENDED": "已停用 · 不可执行"}[record.status]
            body.addWidget(label(status_text, role="stage"))
            actions = page.row(body)
            if record.status == "CANDIDATE":
                approve_button = QPushButton("录入专业确认")
                approve_button.setMinimumHeight(44)
                approve_button.clicked.connect(lambda _=False, item=record: approve(item))
                actions.addWidget(approve_button)
            elif record.status == "APPROVED":
                plan_entry = training_service.get_plan(record.id)
                add_plan = QPushButton("已在计划中" if plan_entry else "加入我的计划")
                add_plan.setMinimumHeight(44)
                add_plan.setEnabled(plan_entry is None)
                add_plan.clicked.connect(lambda _=False, item=record: add_to_plan(item))
                actions.addWidget(add_plan)
                suspend_button = QPushButton("停用资料")
                suspend_button.setMinimumHeight(44)
                suspend_button.setProperty("tone", "danger")
                suspend_button.clicked.connect(lambda _=False, item=record: suspend(item))
                actions.addWidget(suspend_button)
            library_dynamic.addWidget(frame)

        plans = training_service.list_plans()
        if not plans:
            empty, body = card()
            body.addWidget(label("尚无可执行训练计划", role="section"))
            body.addWidget(label("只有已录入专业确认的资料才能加入计划；程序不会自动安排训练。", role="muted"))
            plan_dynamic.addWidget(empty)
        else:
            records_by_id = {item.id: item for item in records}
            for entry in plans:
                exercise = records_by_id.get(entry.exercise_id) or training_service.get_by_id(entry.exercise_id)
                if exercise is None:
                    continue
                frame, body = card()
                body.addWidget(label(exercise.name, role="section"))
                body.addWidget(label("状态：" + ("执行计划中" if entry.status == "ACTIVE" else "已停止"), role="stage"))
                actions = page.row(body)
                if entry.status == "ACTIVE":
                    log_button = QPushButton("记录本次训练")
                    log_button.setMinimumHeight(44)
                    log_button.clicked.connect(lambda _=False, item=exercise: record_log(item))
                    actions.addWidget(log_button)
                    stop_button = QPushButton("停止计划")
                    stop_button.setMinimumHeight(44)
                    stop_button.clicked.connect(lambda _=False, item=exercise: stop_plan(item))
                    actions.addWidget(stop_button)
                else:
                    actions.addWidget(label(f"{entry.stop_reason}。不会再产生训练提醒。", role="muted"))
                plan_dynamic.addWidget(frame)

    def approve(record):
        reviewer, accepted = QInputDialog.getText(page, "录入专业确认", "专业人员姓名 / 标识：")
        if not accepted:
            return
        try:
            training_service.approve(record.id, reviewer)
        except (ValueError, LookupError) as error:
            show_error(str(error))
            return
        refresh()

    def add_to_plan(record):
        try:
            training_service.add_to_plan(record.id)
        except (ValueError, LookupError) as error:
            show_error(str(error))
            return
        refresh()
        page.tab_widget.setCurrentIndex(1)

    def suspend(record):
        answer = QMessageBox.question(page, "停用训练资料", f"停用“{record.name}”？活动计划也会停止。")
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            training_service.suspend(record.id, "用户主动停用")
        except (ValueError, LookupError) as error:
            show_error(str(error))
            return
        refresh()

    def stop_plan(record):
        try:
            training_service.stop_plan(record.id)
        except (ValueError, LookupError) as error:
            show_error(str(error))
            return
        refresh()

    def record_log(record):
        values = _training_log_editor(page)
        if values is None:
            return
        if not values["user_response"]:
            show_error("请填写本次感受；如有不适，请先停止相关训练。")
            return
        try:
            training_service.record_log(record.id, **values)
        except (ValueError, LookupError) as error:
            show_error(str(error))
            return
        QMessageBox.information(page, "已记录", "本次训练记录已保存在本机。")

    def add_candidate():
        record = _exercise_editor(page)
        if record is None:
            return
        try:
            training_service.save_candidate(record)
        except ValueError as error:
            show_error(str(error))
            return
        refresh()

    add_button.clicked.connect(add_candidate)
    page.refresh_training = refresh
    refresh()
    page.finish("训练资料和日志保存在本机 · 不自动推荐、不自动排程；出现不适可立即停止并记录")
    return page


def statistics_page(statistics_service=None):
    page = DesignPage("数据统计", "查看坐姿时长、症状变化与起身次数；不自动判断病情改善。", "Phase 4C：统计与趋势，")
    period = QComboBox()
    period.addItems(("最近 7 天", "最近 30 天"))
    period.setAccessibleName("统计时间范围")
    period.setToolTip("只读取本机已保存记录；缺失日期不会补成 0")
    page.body.addWidget(period)
    page.tab_widget, bodies = tabs(page.body, ("坐姿时长", "症状变化", "起身次数"))
    page._statistics_service = statistics_service
    page._statistics_period = period
    page._statistics_charts = {}
    page._statistics_metrics = {}

    definitions = (
        ("sitting", "坐姿时长", ("已确认坐姿总时长", "有已确认数据的天数")),
        ("symptoms", "症状变化", ("已记录天数", "有疼痛评分的天数")),
        ("up", "起身次数", ("已确认起身次数", "有起身数据的天数")),
    )
    for mode, title, metric_names, body in zip(
        (item[0] for item in definitions),
        (item[1] for item in definitions),
        (item[2] for item in definitions),
        bodies,
    ):
        panel, chart = card()
        chart.addWidget(label(f"{title}趋势", role="section"))
        trend = StatisticsChart(mode)
        chart.addWidget(trend)
        page._statistics_charts[mode] = trend
        row = page.row(chart)
        page._statistics_metrics[mode] = []
        for name in metric_names:
            metric, box = card()
            box.addWidget(label(name, role="muted"))
            value = label("—", role="metric")
            hint = label("统计服务未接入" if statistics_service is None else "暂无记录", role="muted")
            box.addWidget(value)
            box.addWidget(hint)
            page._statistics_metrics[mode].append((value, hint))
            row.addWidget(metric, 1)
        body.addWidget(panel)
        body.addStretch()

    page.feedback = label(role="muted")
    page.feedback.hide()
    page.body.addWidget(page.feedback)

    def format_minutes(seconds):
        if seconds is None:
            return "—"
        minutes = seconds // 60
        hours, remainder = divmod(minutes, 60)
        return f"{hours} 小时 {remainder} 分" if hours else f"{remainder} 分"

    def set_metric(mode, index, value, hint):
        metric, metric_hint = page._statistics_metrics[mode][index]
        metric.setText(value)
        metric_hint.setText(hint)

    def refresh():
        days = 7 if period.currentIndex() == 0 else 30
        if statistics_service is None:
            rows = ()
            page.status.setText("统计页已搭建 · 统计服务尚未接入")
            page.feedback.setText("当前仅展示页面结构；不生成演示曲线，也不把缺失记录补为 0。")
            page.feedback.show()
        else:
            try:
                rows = statistics_service.recent(days)
            except Exception:
                logging.getLogger(__name__).exception("Could not load statistics")
                rows = ()
                page.feedback.setText("统计读取失败，未显示伪造结果；详见本机日志。")
                page.feedback.show()
            else:
                page.status.setText("统计服务已接入 · 仅展示本机已保存记录")
                page.feedback.setText(
                    "未知区间单独展示，不计入已确认坐姿；统计不代表病情改善或医疗结论。"
                )
                page.feedback.show()

        for chart in page._statistics_charts.values():
            chart.set_rows(rows)

        if statistics_service is None:
            for mode in page._statistics_metrics:
                for index in range(2):
                    set_metric(mode, index, "—", "统计服务未接入")
            return

        confirmed_sitting = [row.sitting_seconds for row in rows if row.sitting_seconds is not None]
        uncertain_sitting = [row.uncertain_sitting_seconds for row in rows if row.uncertain_sitting_seconds is not None]
        symptom_rows = [row for row in rows if row.symptom_recorded]
        scored_rows = [row for row in symptom_rows if row.pain_score is not None]
        up_rows = [row for row in rows if row.up_count is not None]
        total_sitting = sum(confirmed_sitting) if confirmed_sitting else None
        total_up = sum(row.up_count for row in up_rows) if up_rows else None
        set_metric("sitting", 0, format_minutes(total_sitting), f"{len(confirmed_sitting)} 天有已确认记录")
        if uncertain_sitting:
            set_metric("sitting", 1, str(len(confirmed_sitting)), f"另有 {format_minutes(sum(uncertain_sitting))} 未知区间")
        else:
            set_metric("sitting", 1, str(len(confirmed_sitting)) if confirmed_sitting else "—", "按本地日期统计")
        set_metric("symptoms", 0, str(len(symptom_rows)) if symptom_rows else "—", "未填写疼痛评分仍算已记录")
        set_metric("symptoms", 1, str(len(scored_rows)) if scored_rows else "—", "缺失评分不会补成 0")
        set_metric("up", 0, f"{total_up} 次" if total_up is not None else "—", "只统计人工确认起身")
        set_metric("up", 1, str(len(up_rows)) if up_rows else "—", "按本地日期统计")

    period.currentIndexChanged.connect(refresh)
    page.refresh_history = refresh
    page.finish("数据保留在本机 · 只展示已保存证据，未知区间与缺失症状不会被静默补值")
    refresh()
    return page


def preview_dialog(parent, kind):
    """UI-only preview. Never touches posture, database or OS notifications."""
    dialog = QDialog(parent)
    dialog.setObjectName("designPreview")
    dialog.setWindowTitle("界面预览 · 不触发实际操作")
    dialog.setWindowIcon(parent.windowIcon())
    dialog.setStyleSheet(parent.styleSheet())
    dialog.setMinimumWidth(280)
    dialog.resize(min(500, max(280, parent.width() - 40)), 360)
    body = QVBoxLayout(dialog)
    body.setContentsMargins(20, 20, 20, 20)
    body.setSpacing(16)
    body.addWidget(label(f"{APP_NAME} · 设计预览", role="section"))
    body.addWidget(label("仅预览样式 · 不改变计时，不发通知，不记录已读", role="stage"))
    if kind == "startup":
        body.addWidget(label("现在正在坐着吗？", role="title"))
        body.addWidget(label("实际姿势仍需通过主界面的人工确认按钮设置。", role="muted"))
        art = Illustration("sitting.svg")
        art.setFixedSize(110, 90)
        body.addWidget(art, 0, Qt.AlignmentFlag.AlignCenter)
        for title in ("现在坐着（预览）", "现在未坐着（预览）"):
            pending_button(title, body, "预览不提供真实姿势确认，请返回首页操作")
        checkbox = QCheckBox("不再显示（未开放）")
        checkbox.setEnabled(False)
        checkbox.setToolTip("默认启动必须先确认；此偏好未实现")
        body.addWidget(checkbox)
    elif kind == "warning":
        body.addWidget(label("温馨提醒", role="title"))
        text = label("您已经坐了 35 分钟了\n可以起身活动一下，放松腰椎。", name="notice")
        text.setProperty("tone", "warning")
        body.addWidget(text)
        body.addWidget(label("实际 35 分钟通知由 Windows 展示；系统可能抑制通知。", role="muted"))
    elif kind == "limit":
        body.addWidget(label("您已经坐了 40 分钟", role="title"))
        text = label("请现在起身改变姿势，不要继续久坐。", name="notice")
        text.setProperty("tone", "danger")
        body.addWidget(text)
        pending_button("我已起身（预览）", body, "预览不会结束周期")
        pending_button("知道了（预览，仅已读）", body, "预览不会确认已读")
        body.addWidget(label("实际应用中：“知道了”不代表起身，也不会重置计时。", role="muted"))
    else:
        raise ValueError(f"Unknown preview: {kind}")
    close = QPushButton("关闭预览")
    close.setMinimumHeight(44)
    close.clicked.connect(dialog.accept)
    body.addWidget(close)
    dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    dialog.show()
    close.setFocus()
    return dialog


def add_preview(layout, title, kind, window):
    button = QPushButton(title)
    button.setMinimumHeight(44)
    button.clicked.connect(lambda: preview_dialog(window, kind))
    layout.addWidget(button)
    return button


def settings_page(window):
    page = DesignPage("设置", "本地运行、开机常驻与提醒偏好；可用项和待实现项分开。", "Phase 4D：完整设置，")
    page.status.setText("托盘与登录启动已有适配器 · 其余偏好 / 数据管理待实现")
    local = page.section("本地运行 · 保护隐私")
    local.addWidget(label("核心数据保存在本机，不默认上传健康数据、不启用遥测。", role="muted"))
    row = page.row(local)
    for title in ("备份 / 恢复 · 待实现", "删除本地记录 · 待实现"):
        pending_button(title, row)
    startup = page.section("开机常驻 · 系统托盘")
    page.startup_check = QCheckBox("登录 Windows 时启动")
    page.startup_check.setMinimumHeight(44)
    page.startup_check.setEnabled(False)
    page.startup_check.setToolTip("启动适配器未绑定；截图 / 测试预览不会修改 Windows 启动项")
    startup.addWidget(page.startup_check)
    page.startup_status = label("启动适配器未绑定；实际应用启动后读取当前用户设置", role="muted")
    startup.addWidget(page.startup_status)
    startup.addWidget(label("窗口关闭后保留托盘运行；只有托盘可用时才能继续后台提醒。", role="muted"))
    reminder = page.section("定时提醒 · 35 / 40 分钟")
    reminder.addWidget(label("当前规则：35 分钟普通提醒，40 分钟明显警示；之后每 5 分钟最多重复 3 次。不必坐满。", role="muted"))
    row = page.row(reminder)
    add_preview(row, "35 分钟提醒预览", "warning", window)
    add_preview(row, "40 分钟提醒预览", "limit", window)
    for title in ("提醒声音（待实现）", "重复提醒（待实现）"):
        check = QCheckBox(title)
        check.setMinimumHeight(44)
        check.setEnabled(False)
        reminder.addWidget(check)
    reminder.addWidget(label("禁用控件不是当前配置；本轮不调整已实现的提醒规则。", role="muted"))
    startup_preview = page.section("启动与恢复确认")
    add_preview(startup_preview, "查看开机启动询问样式", "startup", window)
    startup_preview.addWidget(label("实际启动和恢复核实仍在首页状态卡完成；独立弹窗只提供设计预览。", role="muted"))
    page.finish()
    return page


def help_page(window):
    page = DesignPage("帮助与功能进度", "每个设计稿入口都可访问；占位页不等于业务已交付。", "后续分期，")
    page.status.setText("已实现：人工计时 / 阈值提醒 / 中断待核实 · 以下业务按阶段接入")
    guide = page.section("日常操作")
    guide.addWidget(label("首页先确认姿势。起身后点击“我已起身”，重新坐下时再次确认；键鼠活动不用于判断真实姿势。关闭到托盘后仍运行；主动退出后停止提醒。", role="muted"))
    pending_button("修正误操作 · 待实现", guide)
    progress = page.section("后续实施顺序")
    for title, detail in (
        ("Phase 4A · 症状记录", "保存、编辑 / 删除、CSV 导出、异常症状提示及规则测试"),
        ("Phase 4B · 康复训练", "资料来源、专业确认、候选 / 已确认 / 停用状态、计划及不适日志"),
        ("Phase 4C · 统计趋势", "今日统计、7 / 30 天趋势；未知区间和缺失症状不补 0"),
        ("Phase 4D · 设置与交互收口", "提醒偏好、数据备份管理、启动询问交互、误操作修正"),
        ("Phase 5 / 6 · 可靠性与交付", "真实锁屏 / 休眠 / 崩溃 / 时钟变化验证，随后打包与实际试用"),
    ):
        progress.addWidget(label(title, role="field"))
        progress.addWidget(label(detail, role="muted"))
    preview = page.section("设计板交互预览（不会改变真实状态）")
    for title, kind in (("开机启动询问", "startup"), ("35 分钟普通提醒", "warning"), ("40 分钟明显提醒", "limit")):
        add_preview(preview, title, kind, window)
    page.finish()
    return page


def build_pages(window, symptom_service=None, training_service=None, statistics_service=None):
    return {"record": symptoms_page(symptom_service), "training": training_page(training_service), "chart": statistics_page(statistics_service),
            "settings": settings_page(window), "info": help_page(window)}
