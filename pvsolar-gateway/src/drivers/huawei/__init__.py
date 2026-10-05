"""
Huawei inverter driver.

Supports:
- SUN2000 series (L0, L1, M0, M1, M2, M3, MA, MB0)
- Modbus TCP/RTU
- SUN2000 with Smart Dongle
"""

from .driver import HuaweiDriver

__all__ = ['HuaweiDriver']
