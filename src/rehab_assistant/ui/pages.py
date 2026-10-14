"""Design-board page skeletons. No health persistence or training execution here."""
import logging
from datetime import date

from PySide6.QtCore import QDate, QSize, Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QBoxLayout, QCheckBox, QComboBox, QDateEdit, QDialog,
    QFileDialog, QGridLayout, QHeaderView, QHBoxLayout, QLayout, QMessageBox,
    QPushButton, QSizePolicy, QSlider, QTableWidget, QTableWidgetItem,
    QTabWidget, QTextEdit, QToolButton, QVBoxLayout, QWidget,
)
from rehab_assistant.domain.symptoms import SymptomRecord
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

    def finish(self):
        self.body.addWidget(label("数据保留在本机 · 页面占位不生成健康记录，也不安排训练", role="muted"))
        self.body.addStretch()


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


def training_page():
    page = DesignPage("康复训练", "资料候选与执行计划分开；未经专业确认，不安排训练。", "Phase 4B：训练库与计划，")
    page.tab_widget, (library, plan) = tabs(page.body, ("康复动作", "我的计划"))
    library.addWidget(label("下列为设计稿动作卡占位，不是实际动作资料或对你的训练建议。", role="muted"))
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
        library.addWidget(frame)
    pending_button("添加动作资料 · 待实现", library)
    library.addWidget(label("专业确认状态由用户手动录入，程序无法验证。初始可执行训练为空；这里的占位动作不进入执行计划。", role="muted"))
    empty, body = card()
    body.addWidget(label("尚无可执行训练计划", role="section"))
    body.addWidget(label("计划服务待实现。后续仅允许专业人员确认过的动作加入计划；出现不适时可立即停止并记录。", role="muted"))
    for text in ("启用训练提醒 · 待实现", "训练日志 / 不适 · 待实现"):
        pending_button(text, body)
    plan.addWidget(empty)
    plan.addStretch()
    page.finish()
    return page


def statistics_page():
    page = DesignPage("数据统计", "查看坐姿时长、症状变化与起身次数；不自动判断病情改善。", "Phase 4C：统计与趋势，")
    period = QComboBox()
    period.addItems(("最近 7 天", "最近 30 天"))
    period.setAccessibleName("统计时间范围，数据待接入")
    page.body.addWidget(period)
    page.tab_widget, bodies = tabs(page.body, ("坐姿时长", "症状变化", "起身次数"))
    for title, body in zip(("坐姿时长", "症状变化", "起身次数"), bodies):
        panel, chart = card()
        chart.addWidget(label(f"{title}趋势", role="section"))
        placeholder = label("趋势图占位\n\n统计服务尚未接入\n不生成演示曲线，也不把缺失记录补为 0", role="chartPlaceholder")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setMinimumHeight(200)
        chart.addWidget(placeholder)
        row = page.row(chart)
        for name in ("日均坐姿时长", "日均起身次数") if title != "症状变化" else ("记录天数", "疼痛评分"):
            metric, box = card()
            box.addWidget(label(name, role="muted"))
            box.addWidget(label("—", role="metric"))
            box.addWidget(label("数据待接入", role="muted"))
            row.addWidget(metric, 1)
        body.addWidget(panel)
        body.addStretch()
    pending_button("导出统计 · 待实现", page.body)
    page.finish()
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
    body.addWidget(label("腰椎康复助手 · 设计预览", role="section"))
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


def build_pages(window, symptom_service=None):
    return {"record": symptoms_page(symptom_service), "training": training_page(), "chart": statistics_page(),
            "settings": settings_page(window), "info": help_page(window)}
