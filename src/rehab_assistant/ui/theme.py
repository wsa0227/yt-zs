"""Light-blue Windows desktop tokens, following the supplied design board."""

COLORS = {
    "background": "#F4F9FF", "surface": "#FFFFFF", "hero": "#FFFFFF",
    "sidebar": "#EAF3FD", "text": "#102747", "muted": "#526A89",
    "primary": "#1265E7", "hover": "#0E54C5", "pressed": "#0B449F",
    "border": "#DCE8F5", "track": "#E9EFF5", "green": "#38BF87",
    "success": "#168453", "warning": "#8A530E", "warning_bg": "#FFF5E5",
    "danger": "#B52330", "danger_bg": "#FFF0F1", "focus": "#174A89",
}


def stylesheet() -> str:
    c = COLORS
    return f"""
    QMainWindow, QWidget#shell, QWidget#page {{ background: {c['background']}; }}
    QWidget {{ font-family: "Microsoft YaHei UI", "Segoe UI"; font-size: 14px; color: {c['text']}; }}
    QLabel {{ background: transparent; border: none; }}
    QLabel[role="muted"] {{ color: {c['muted']}; font-size: 13px; }}
    QLabel[role="title"] {{ font-size: 23px; font-weight: 600; }}
    QLabel[role="section"] {{ font-size: 17px; font-weight: 600; }}
    QLabel[role="metric"] {{ font-size: 25px; font-weight: 600; }}
    QLabel[role="brand"] {{ font-size: 16px; font-weight: 600; }}
    QWidget#sidebar {{ background: {c['sidebar']}; border-right: 1px solid {c['border']}; }}
    QFrame[role="card"] {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 14px; }}
    QFrame[role="statCard"] {{ background: #F8FBFF; border: 1px solid {c['border']}; border-radius: 12px; }}
    QLabel#statusBadge {{ color: {c['success']}; font-size: 23px; font-weight: 600; }}
    QLabel#statusBadge[tone="warning"] {{ color: {c['warning']}; }}
    QLabel#statusBadge[tone="danger"] {{ color: {c['danger']}; }}
    QLabel#statusBadge[tone="neutral"] {{ color: {c['muted']}; }}
    QLabel#statusDot {{ background: {c['green']}; border-radius: 5px; }}
    QLabel#statusDot[tone="neutral"] {{ background: {c['muted']}; }}
    QLabel#statusDot[tone="warning"] {{ background: {c['warning']}; }}
    QLabel#statusDot[tone="danger"] {{ background: {c['danger']}; }}
    QLabel#elapsed {{ font-family: "Segoe UI", "Microsoft YaHei UI"; font-size: 39px; font-weight: 600; }}
    QLabel#elapsed[compact="true"] {{ font-size: 31px; }}
    QLabel#elapsed[tiny="true"] {{ font-size: 24px; }}
    QLabel#headline {{ font-size: 18px; font-weight: 600; }}
    QLabel#notice {{ color: {c['muted']}; padding: 12px 14px; background: #F1F7FD; border-radius: 8px; }}
    QLabel#notice[tone="warning"] {{ color: {c['warning']}; background: {c['warning_bg']}; }}
    QLabel#notice[tone="danger"] {{ color: {c['danger']}; background: {c['danger_bg']}; }}
    QLabel#errorMessage {{ color: {c['danger']}; background: {c['danger_bg']}; padding: 12px; border-radius: 8px; }}
    QPushButton {{ background: {c['surface']}; color: {c['text']}; border: 2px solid {c['border']};
        border-radius: 8px; padding: 8px 12px; font-weight: 600; min-height: 24px; }}
    QPushButton:hover {{ background: #EFF6FF; border-color: #A7C9F5; }}
    QPushButton:pressed {{ background: #DEECFD; border-color: {c['primary']}; }}
    QPushButton[role="primary"] {{ background: {c['primary']}; color: white; border-color: {c['primary']}; }}
    QPushButton[role="primary"]:hover {{ background: {c['hover']}; border-color: {c['hover']}; }}
    QPushButton[role="primary"]:pressed {{ background: {c['pressed']}; border-color: {c['pressed']}; }}
    QPushButton[tone="danger"] {{ background: #D93240; border-color: #D93240; color: white; }}
    QPushButton[tone="danger"]:hover {{ background: #BF2734; border-color: #BF2734; }}
    QPushButton[tone="danger"]:pressed {{ background: #A7212C; border-color: #A7212C; }}
    QPushButton:focus {{ border: 2px solid {c['focus']}; }}
    QPushButton[role="primary"]:focus, QPushButton[tone="danger"]:focus {{ border: 2px solid #9FC7FF; }}
    QPushButton:disabled {{ background: #F2F5F9; color: {c['muted']}; border-color: {c['border']}; }}
    QPushButton[role="nav"] {{ background: transparent; border: 2px solid transparent; text-align: left;
        padding: 10px 12px; font-weight: 400; border-radius: 7px; }}
    QPushButton[role="nav"]:checked {{ background: #D4E7FF; color: #105CC4; border-left: 2px solid {c['primary']}; font-weight: 600; }}
    QPushButton[role="nav"]:hover {{ background: #E0EDFC; }}
    QPushButton[role="nav"]:disabled {{ background: transparent; color: {c['muted']}; }}
    QPushButton[role="nav"]:focus {{ border: 2px solid {c['focus']}; }}
    QScrollArea {{ background: transparent; border: none; }}
    QScrollBar:vertical {{ background: {c['background']}; width: 10px; margin: 0; }}
    QScrollBar::handle:vertical {{ background: #C2D3E6; min-height: 32px; border-radius: 5px; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
    QWidget#designPage, QDialog#designPreview {{ background: {c['background']}; }}
    QToolButton[role="capability"] {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #EAF4FF, stop:1 #DFEDFC);
        color: {c['text']}; border: 2px solid transparent; border-radius: 12px; padding: 8px 2px; font-size: 13px; }}
    QToolButton[role="capability"]:hover {{ background: #D8EAFE; border-color: #A7C9F5; }}
    QToolButton[role="capability"]:pressed {{ background: #C9DFFA; }}
    QToolButton[role="capability"]:focus {{ border-color: {c['focus']}; }}
    QLabel[role="stage"] {{ background: #EAF3FD; color: {c['muted']}; padding: 12px; border-radius: 8px; font-size: 13px; }}
    QLabel[role="field"] {{ font-weight: 600; }}
    QLabel[role="artPlaceholder"], QLabel[role="chartPlaceholder"] {{ background: #F4F9FF;
        color: {c['muted']}; border: 1px dashed #B9CFE7; border-radius: 10px; padding: 16px; }}
    QComboBox, QDateEdit, QTextEdit {{ background: {c['surface']}; border: 2px solid {c['border']};
        border-radius: 8px; padding: 8px; selection-background-color: {c['primary']}; }}
    QComboBox, QDateEdit {{ min-height: 26px; }}
    QComboBox:focus, QDateEdit:focus, QTextEdit:focus {{ border-color: {c['focus']}; }}
    QCheckBox {{ spacing: 8px; }}
    QCheckBox::indicator {{ width: 18px; height: 18px; border: 2px solid #A7BED8;
        border-radius: 4px; background: white; }}
    QCheckBox::indicator:checked {{ background: {c['primary']}; border-color: {c['primary']}; }}
    QCheckBox:focus {{ color: {c['primary']}; }}
    QCheckBox:disabled {{ color: {c['muted']}; }}
    QSlider::groove:horizontal {{ background: #DFE9F4; height: 6px; border-radius: 3px; }}
    QSlider::sub-page:horizontal {{ background: {c['green']}; border-radius: 3px; }}
    QSlider::handle:horizontal {{ background: {c['success']}; width: 18px; margin: -7px 0; border-radius: 9px; }}
    QSlider:focus::handle:horizontal {{ border: 2px solid {c['focus']}; }}
    QTabWidget::pane {{ border: none; background: transparent; }}
    QTabBar::tab {{ padding: 12px 8px; color: {c['muted']}; border-bottom: 2px solid transparent; }}
    QTabBar::tab:selected {{ color: {c['primary']}; border-bottom-color: {c['primary']}; background: #EAF3FD; }}
    QTabBar::tab:focus {{ border-color: {c['focus']}; }}
    """
