#!/usr/bin/env python3
"""Compatibility entry point for the relocated history scanner."""

import os
from pathlib import Path
import sys


target = (
    Path(__file__).resolve().parents[2]
    / "reproducers/rrc-signaling-storm/analysis/check_sensitive_history.py"
)
os.execv(sys.executable, [sys.executable, str(target), *sys.argv[1:]])
