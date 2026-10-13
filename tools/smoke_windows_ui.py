"""Short native startup smoke test with isolated data and IPC identity."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

os.environ["QT_QPA_PLATFORM"] = "windows"

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
import rehab_assistant.app as app_module


def main():
    app = QApplication([])
    observed = []

    def check():
        try:
            windows = [w for w in app.topLevelWidgets() if isinstance(w, app_module.MainWindow) and w.isVisible()]
            assert len(windows) == 1, f"Expected one visible main window, got {len(windows)}"
            window = windows[0]
            assert window._posture.state.posture == "UNKNOWN"
            assert window._elapsed.text() == "--:--"
            assert window._environment._wts_registered, "WTS registration failed"
            assert window.centralWidget().horizontalScrollBar().maximum() == 0
            print(f"platform={app.platformName()} visible=True wts_registered=True "
                  f"size={window.width()}x{window.height()}")
            observed.append(True)
        finally:
            app.quit()

    with TemporaryDirectory(prefix="rehab-ui-smoke-") as directory:
        with (
            patch.object(app_module, "data_directory", return_value=Path(directory)),
            patch.object(app_module, "APP_ID", f"rehab-ui-smoke-{uuid4().hex}"),
            patch.object(app_module.autostart, "is_enabled", return_value=False),
        ):
            QTimer.singleShot(1200, check)
            result = app_module.main()
            assert result == 0, result
            assert observed == [True], "Startup check did not complete"
            print(f"startup_exit_code={result}")


if __name__ == "__main__":
    main()
