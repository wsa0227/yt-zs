"""Windows packaging preflight; never claims that an artifact was built."""

from __future__ import annotations

import argparse
import importlib.util
import os
import platform
import struct
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "lumbar-rehab-assistant.spec"
ENTRY = ROOT / "src" / "rehab_assistant" / "__main__.py"
ASSETS = ROOT / "src" / "rehab_assistant" / "ui" / "assets"
INSTALLER = ROOT / "installer" / "yu-an.iss"


def _check(label: str, passed: bool, detail: str) -> bool:
    print(f"[{'PASS' if passed else 'FAIL'}] {label}: {detail}")
    return passed


def resolve_iscc(explicit_path: str | None = None) -> Path | None:
    """Use an explicit compiler, PATH, then conventional per-user/system installs."""
    if explicit_path is not None:
        candidate = Path(explicit_path).expanduser()
        return candidate.resolve() if candidate.is_file() else None
    on_path = shutil.which("iscc.exe") or shutil.which("iscc")
    if on_path:
        return Path(on_path).resolve()
    locations = (
        ("LOCALAPPDATA", Path("Programs") / "Inno Setup 6" / "ISCC.exe"),
        ("ProgramFiles(x86)", Path("Inno Setup 6") / "ISCC.exe"),
        ("ProgramFiles", Path("Inno Setup 6") / "ISCC.exe"),
    )
    for variable, suffix in locations:
        base = os.environ.get(variable)
        if base:
            candidate = Path(base) / suffix
            if candidate.is_file():
                return candidate.resolve()
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-installer", action="store_true", help="check EXE-only prerequisites")
    parser.add_argument("--iscc-path", help="explicit Inno Setup compiler executable")
    parser.add_argument("--print-iscc-path", action="store_true", help="print only the resolved compiler path")
    args = parser.parse_args(argv)
    if args.print_iscc_path:
        compiler = resolve_iscc(args.iscc_path)
        if compiler is None:
            print("Inno Setup compiler was not found", file=sys.stderr)
            return 1
        print(compiler)
        return 0

    required_ok = True
    required_ok &= _check("platform", sys.platform == "win32", f"{sys.platform} (target Windows)")
    machine = platform.machine()
    pointer_bits = struct.calcsize("P") * 8
    required_ok &= _check(
        "architecture", machine.casefold() in {"amd64", "x86_64"} and pointer_bits == 64,
        f"{machine}, {pointer_bits}-bit Python (target native Windows x64)",
    )
    required_ok &= _check(
        "Python", sys.version_info[:2] == (3, 12),
        f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
    )
    required_ok &= _check("PySide6", importlib.util.find_spec("PySide6") is not None, "importable")
    required_ok &= _check("PyInstaller", importlib.util.find_spec("PyInstaller") is not None, "importable")

    for label, path in (("spec", SPEC), ("entry point", ENTRY), ("installer config", INSTALLER)):
        if label == "installer config" and args.skip_installer:
            continue
        required_ok &= _check(label, path.is_file(), str(path))
    asset_files = sorted(ASSETS.glob("*.svg")) if ASSETS.is_dir() else []
    required_ok &= _check("SVG assets", bool(asset_files), f"{len(asset_files)} file(s) under {ASSETS}")

    if args.skip_installer:
        print("[SKIP] Inno Setup compiler: EXE-only build requested")
    else:
        iscc = resolve_iscc(args.iscc_path)
        required_ok &= _check("Inno Setup compiler", iscc is not None, str(iscc) if iscc else "not found (explicit path, PATH or standard install directories)")

    if not required_ok:
        print("RESULT=NOT_READY required prerequisites are missing")
        return 1
    print("RESULT=READY prerequisites verified (no build performed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
