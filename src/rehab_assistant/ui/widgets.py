"""Display-only vector artwork and elapsed-time ring; no posture detection."""

from math import cos, sin, tau
from pathlib import Path

from PySide6.QtCore import QByteArray, QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QWidget

from .theme import COLORS

ASSETS = Path(__file__).parent / "assets"

# One consistent, round-ended outline family, drawn from local vector paths.
ICON_PATHS = {
    "shield": '<path d="M12 2 3 6v6c0 5 9 10 9 10s9-5 9-10V6z"/><path d="m8 11 3 3 5-5"/>',
    "monitor": '<rect x="3" y="3" width="18" height="13" rx="2"/><path d="M12 16v5M7 21h10"/>',

    "home": '<path d="m3 11 9-8 9 8M6 10v11h12V10M10 21v-7h4v7"/>',
    "record": '<rect x="5" y="5" width="14" height="16" rx="2"/><path d="M9 5V3h6v2M8 13l3 3 5-6"/>',
    "training": '<path d="M3 8v8m3-11v14m3-7h6m3-7v14m3-11v8"/>',
    "chart": '<path d="M5 20v-7m7 7V4m7 16V9"/>',
    "settings": '<circle cx="12" cy="12" r="4"/><path d="M12 2v3m0 14v3M2 12h3m14 0h3M5 5l2 2m10 10 2 2M5 19l2-2M17 7l2-2"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 6v6l4 2"/>',
    "bell": '<path d="M5 17h14l-2-3V9a5 5 0 0 0-10 0v5zM10 21h4M12 2v2"/>',
    "up": '<circle cx="13" cy="4" r="2"/><path d="m11 8-2 6-3 6m5-12 3 6 3 6M11 8l6 3 3-1M11 9l-5 3-2 4"/>',
    "pause": '<path d="M8 5v14M16 5v14"/>',
    "check": '<path d="m4 12 5 5L20 6"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7v.1"/>',
    "warning": '<path d="m12 3 10 18H2zM12 9v5M12 17v.1"/>',
}


def icon(name, color=None):
    """Produce multi-resolution icons without remote assets or font glyphs."""
    color = color or COLORS["primary"]
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
           f'fill="none" stroke="{color}" stroke-width="1.8" stroke-linecap="round" '
           f'stroke-linejoin="round">{ICON_PATHS[name]}</svg>')
    renderer = QSvgRenderer(QByteArray(svg.encode()))
    result = QIcon()
    for size in (24, 48, 72):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        result.addPixmap(pixmap)
    return result


def brand_icon():
    return QIcon(str(ASSETS / "brand.svg"))


class Illustration(QWidget):
    def __init__(self, asset, parent=None):
        super().__init__(parent)
        self._asset = None
        self.set_asset(asset)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def set_asset(self, asset):
        if self._asset == asset:
            return
        self._asset = asset
        if hasattr(self, "_renderer"):
            self._renderer.deleteLater()
        self._renderer = QSvgRenderer(str(ASSETS / asset), self)
        if not self._renderer.isValid():
            raise ValueError(f"Invalid UI artwork: {asset}")
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._renderer.render(painter, QRectF(self.rect()))


class ThresholdRing(QWidget):
    """Clockwise 0–40 minute scale, not an activity/completion goal."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._seconds = None
        self._uncertain = False
        self.setFixedSize(300, 300)
        self.setAccessibleName("坐姿提醒时间刻度：尚无确认计时")
        self.setAccessibleDescription("35 分钟提醒，40 分钟上限；不是必须坐满的目标")
        self.setToolTip("仅按人工确认计时；35 分钟提醒，40 分钟上限，不必坐满")

    @property
    def progress_fraction(self):
        return 0 if self._seconds is None else max(0, min(self._seconds / 2400, 1))

    @property
    def tone(self):
        return ("neutral" if self._seconds is None else "danger" if self._seconds >= 2400
                else "warning" if self._seconds >= 2100 else "normal")

    def set_seconds(self, seconds, uncertain=False):
        if (seconds, uncertain) == (self._seconds, self._uncertain):
            return
        self._seconds, self._uncertain = seconds, uncertain
        self.setAccessibleName(
            "坐姿提醒时间刻度：尚无确认计时" if seconds is None else
            f"坐姿提醒时间刻度：{'推算' if uncertain else '已过'} {seconds // 60} 分 {seconds % 60} 秒；40 分钟上限"
        )
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(17, 17, self.width() - 34, self.height() - 34)
        painter.setPen(QPen(QColor(COLORS["track"]), 11))
        painter.drawEllipse(rect)
        if self._seconds is not None and self._seconds > 0:
            color = {"normal": "green", "warning": "warning", "danger": "danger"}[self.tone]
            pen = QPen(QColor(COLORS[color]), 11, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawArc(rect, 90 * 16, -round(360 * 16 * self.progress_fraction))
        # The distinct 35/40 ticks prevent the ring from suggesting a target to fill.
        center, radius = rect.center(), rect.width() / 2
        font = painter.font()
        font.setPixelSize(11)
        painter.setFont(font)
        for minute in (35, 40):
            angle = tau * minute / 40
            x, y = sin(angle), -cos(angle)
            painter.setPen(QPen(QColor(COLORS["muted"] if minute == 35 else COLORS["danger"]), 2))
            painter.drawLine(QPointF(center.x() + x * (radius - 7), center.y() + y * (radius - 7)),
                             QPointF(center.x() + x * (radius + 7), center.y() + y * (radius + 7)))
            painter.drawText(QRectF(center.x() + x * (radius - 22) - 12,
                                    center.y() + y * (radius - 22) - 7, 24, 16),
                             Qt.AlignmentFlag.AlignCenter, str(minute))
