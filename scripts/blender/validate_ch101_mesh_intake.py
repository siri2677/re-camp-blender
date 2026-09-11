#!/usr/bin/env python3
"""Backward-compatible CH101 entry point for the current-roster validator."""

from __future__ import annotations

import sys

from validate_current_roster_mesh_intake import main


def run() -> int:
    separator = sys.argv.index("--") if "--" in sys.argv else 0
    prefix = sys.argv[: separator + 1] if separator else sys.argv[:1]
    arguments = sys.argv[separator + 1 :] if separator else sys.argv[1:]
    if "--character" not in arguments:
        arguments = ["--character", "CH101", *arguments]
    sys.argv[:] = [*prefix, *arguments]
    return main()


if __name__ == "__main__":
    raise SystemExit(run())
