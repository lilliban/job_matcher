"""Configurazione centralizzata del logging.

Uso: `from app.core.logging import setup_logging; setup_logging()` in `app/main.py`.
Personalizzabile via env var `LOG_LEVEL` (default INFO).
"""

from __future__ import annotations

import logging
import os

_FORMAT = "%(asctime)s  %(levelname)-7s  %(name)s  %(message)s"
_DATEFMT = "%H:%M:%S"


def setup_logging(level: str | None = None) -> None:
    """Configura il root logger.

    Idempotente: chiamarla più volte non duplica gli handler.
    """
    resolved = (level or os.environ.get("LOG_LEVEL") or "INFO").upper()

    root = logging.getLogger()
    if root.handlers:
        root.setLevel(resolved)
        return

    logging.basicConfig(level=resolved, format=_FORMAT, datefmt=_DATEFMT)
