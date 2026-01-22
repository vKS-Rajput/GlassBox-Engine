"""
GlassBox CLI entry point.

Usage:
    python -m glassbox.cli run
    python -m glassbox.cli leads
    python -m glassbox.cli explain <id>
    python -m glassbox.cli evidence <id>
"""

import sys
from .main import main

if __name__ == "__main__":
    sys.exit(main())
