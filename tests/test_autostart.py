import sys
import unittest
from unittest.mock import patch

from rehab_assistant.adapters.autostart import set_enabled


class AutoStartTests(unittest.TestCase):
    def test_registry_integration_is_explicitly_windows_only(self):
        with patch.object(sys, "platform", "linux"):
            with self.assertRaisesRegex(OSError, "only on Windows"):
                set_enabled(True)


if __name__ == "__main__":
    unittest.main()
