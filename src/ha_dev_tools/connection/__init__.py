"""Connection implementations for Home Assistant instances."""

from .local import LocalHAConnection
from .api import HAAPIConnection

__all__ = ["LocalHAConnection", "HAAPIConnection"]