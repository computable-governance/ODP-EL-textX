"""
Shared pytest fixtures. Adds toolchain/ to sys.path so tests can import
el_api, el_parser, etc. directly, matching how toolchain/el_api.py itself
adds toolchain/ to sys.path (see its _HERE/_REPO_ROOT pattern).
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLCHAIN = REPO_ROOT / "toolchain"
if str(TOOLCHAIN) not in sys.path:
    sys.path.insert(0, str(TOOLCHAIN))
