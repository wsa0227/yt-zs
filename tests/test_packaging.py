"""Packaging scripts: mode-aware prerequisites and PyInstaller child tracking."""

import sys
from collections import namedtuple
from contextlib import ExitStack, redirect_stdout
from io import StringIO
from pathlib import Path
import unittest
from unittest.mock import patch

from tools import preflight_windows_package as preflight

if sys.platform == "win32":
    from tools import smoke_frozen_exe as smoke


class PreflightTests(unittest.TestCase):
    def setUp(self):
        # Prerequisite tests run without depending on installed packaging tools.
        stack = self.enterContext(ExitStack())
        version = namedtuple("Version", "major minor micro")(3, 12, 12)
        stack.enter_context(patch.object(preflight.sys, "platform", "win32"))
        stack.enter_context(patch.object(preflight.platform, "machine", return_value="AMD64"))
        stack.enter_context(patch.object(preflight.struct, "calcsize", return_value=8))
        stack.enter_context(patch.object(preflight.sys, "version_info", version))
        stack.enter_context(patch.object(preflight.importlib.util, "find_spec", return_value=object()))
        stack.enter_context(patch.object(Path, "is_file", return_value=True))
        stack.enter_context(patch.object(Path, "is_dir", return_value=True))
        stack.enter_context(patch.object(Path, "glob", return_value=[Path("brand.svg")]))
        stack.enter_context(patch.dict(preflight.os.environ, {}, clear=True))
        stack.enter_context(redirect_stdout(StringIO()))

    def test_exe_only_mode_does_not_require_inno(self):
        with patch.object(preflight.shutil, "which", return_value=None):
            self.assertEqual(preflight.main(["--skip-installer"]), 0)

    def test_installer_mode_requires_inno(self):
        with patch.object(preflight.shutil, "which", return_value=None):
            self.assertNotEqual(preflight.main([]), 0)

    def test_exe_only_mode_still_requires_pyinstaller(self):
        with patch.object(preflight.importlib.util, "find_spec", side_effect=[object(), None]):
            self.assertNotEqual(preflight.main(["--skip-installer"]), 0)

    def test_32_bit_python_cannot_create_mislabeled_x64_package(self):
        with patch.object(preflight.struct, "calcsize", return_value=4):
            self.assertNotEqual(preflight.main(["--skip-installer"]), 0)

    def test_native_arm_build_requires_a_separate_target_configuration(self):
        with patch.object(preflight.platform, "machine", return_value="ARM64"):
            self.assertNotEqual(preflight.main(["--skip-installer"]), 0)


class CompilerResolutionTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.dict(preflight.os.environ, {}, clear=True))

    def test_path_compiler_takes_precedence_over_standard_install(self):
        with patch.object(preflight.shutil, "which", return_value="custom/ISCC.exe"):
            self.assertEqual(preflight.resolve_iscc(), Path("custom/ISCC.exe").resolve())

    def test_per_user_install_is_found_without_path_edit(self):
        with patch.object(preflight.shutil, "which", return_value=None), \
                patch.dict(preflight.os.environ, {"LOCALAPPDATA": "user-local"}), \
                patch.object(Path, "is_file", return_value=True):
            expected = Path("user-local/Programs/Inno Setup 6/ISCC.exe").resolve()
            self.assertEqual(preflight.resolve_iscc(), expected)

    def test_explicit_compiler_takes_precedence_over_path(self):
        with patch.object(Path, "is_file", return_value=True), \
                patch.object(preflight.shutil, "which") as lookup:
            self.assertEqual(preflight.resolve_iscc("custom/ISCC.exe"), Path("custom/ISCC.exe").resolve())
            lookup.assert_not_called()

    def test_invalid_explicit_compiler_does_not_silently_fallback(self):
        with patch.object(Path, "is_file", return_value=False), \
                patch.object(preflight.shutil, "which", return_value="other/ISCC.exe") as lookup:
            self.assertIsNone(preflight.resolve_iscc("missing/ISCC.exe"))
            lookup.assert_not_called()

    def test_print_compiler_path_has_no_preflight_output(self):
        output = StringIO()
        compiler = Path("custom/ISCC.exe").resolve()
        with patch.object(preflight, "resolve_iscc", return_value=compiler), redirect_stdout(output):
            self.assertEqual(preflight.main(["--print-iscc-path"]), 0)
        self.assertEqual(output.getvalue(), str(compiler) + "\n")


@unittest.skipUnless(sys.platform == "win32", "requires Windows APIs")
class FrozenProcessTests(unittest.TestCase):
    def test_descendants_include_bootloader_application_and_grandchild(self):
        self.assertEqual(smoke._descendants(10, {11: 10, 12: 11, 13: 99}), {10, 11, 12})

    def test_descendants_do_not_claim_unrelated_process(self):
        self.assertEqual(smoke._descendants(10, {11: 42, 12: 11}), {10})


if __name__ == "__main__":
    unittest.main()
