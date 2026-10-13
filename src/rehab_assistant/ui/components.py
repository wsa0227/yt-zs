"""Small presentation-only primitives shared by desktop pages."""
from PySide6.QtWidgets import QLabel, QFrame, QVBoxLayout


def label(text="", *, role=None, name=None):
    widget = QLabel(text)
    widget.setWordWrap(True)
    if role:
        widget.setProperty("role", role)
    if name:
        widget.setObjectName(name)
    return widget


def card(name=None):
    widget = QFrame()
    widget.setProperty("role", "card")
    if name:
        widget.setObjectName(name)
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(24, 24, 24, 24)
    layout.setSpacing(16)
    return widget, layout
