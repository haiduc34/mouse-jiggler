"""Build a standalone application for the current operating system."""

from __future__ import annotations

from pathlib import Path
import sys


def main() -> None:
    try:
        import PyInstaller.__main__
    except ImportError:
        raise SystemExit(
            "PyInstaller не установлен. Выполните:\n"
            f'"{sys.executable}" -m pip install -r requirements-build.txt\n'
            "Затем повторите сборку."
        ) from None

    project_dir = Path(__file__).resolve().parent
    options = [
        str(project_dir / "main.py"),
        "--noconfirm",
        "--clean",
        "--onefile",
        "--windowed",
        "--name=MouseJiggler",
        f"--distpath={project_dir / 'dist'}",
        f"--workpath={project_dir / 'build' / 'work'}",
        f"--specpath={project_dir / 'build'}",
    ]
    PyInstaller.__main__.run(options)
    print(f"\nГотовый файл находится в каталоге: {project_dir / 'dist'}")


if __name__ == "__main__":
    main()
