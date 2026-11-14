"""Stub heavy optional dependencies so pure-function tests run without extras."""
import sys
from unittest.mock import MagicMock

for _mod in [
    "sqlalchemy",
    "sqlalchemy.orm",
    "sqlalchemy.exc",
    "httpx",
]:
    sys.modules.setdefault(_mod, MagicMock())
