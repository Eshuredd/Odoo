from collections.abc import Callable
from datetime import datetime

from app.db.base import utc_now

Clock = Callable[[], datetime]

__all__ = ["Clock", "utc_now"]
