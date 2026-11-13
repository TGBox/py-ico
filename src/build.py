import sys

import PyInstaller.__main__


def main() -> None:
    """Build the standalone py-ico executable with PyInstaller."""
    args = (
        sys.argv[1:]
        if len(sys.argv) > 1
        else [
            "--noconfirm",
            "--onedir",
            "--windowed",
            "--hidden-import=src.gui.app",
            "src/main.py",
            "--name",
            "py-ico",
        ]
    )
    PyInstaller.__main__.run(args)


if __name__ == "__main__":
    main()
