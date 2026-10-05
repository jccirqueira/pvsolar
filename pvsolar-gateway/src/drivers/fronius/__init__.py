"""
Fronius inverter driver with SunSpec support.

Supports:
- GEN24 / Tauro series
- SnapINverter via Datamanager 2.0
"""

from .driver import FroniusDriver

__all__ = ['FroniusDriver']
