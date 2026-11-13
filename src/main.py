from __future__ import annotations

import sys
from collections.abc import Sequence

from src.cli import run_cli


def main(argv: Sequence[str] | None = None) -> int:
    """Launch the CLI when arguments are provided, or the desktop GUI otherwise."""
    args = list(sys.argv[1:] if argv is None else argv)
    if args:
        return run_cli(args)

    from src.gui.app import run_gui

    return run_gui()


if __name__ == "__main__":
    raise SystemExit(main())
