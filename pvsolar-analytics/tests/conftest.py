"""pytest configuration for pvSolar Analytics tests."""

import sys
from pathlib import Path

# Add src/ to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
