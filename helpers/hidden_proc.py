"""Run child processes without flashing a Windows console."""

from __future__ import annotations

import subprocess
import sys

CREATE_NO_WINDOW = 0x08000000
CREATE_NEW_PROCESS_GROUP = 0x00000200


def hidden_flags() -> int:
    if sys.platform != "win32":
        return 0
    return CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP


def run(cmd, **kwargs):
    if sys.platform == "win32" and "creationflags" not in kwargs:
        kwargs["creationflags"] = hidden_flags()
    return subprocess.run(cmd, **kwargs)


def popen(cmd, **kwargs):
    if sys.platform == "win32" and "creationflags" not in kwargs:
        kwargs["creationflags"] = hidden_flags()
    return subprocess.Popen(cmd, **kwargs)
