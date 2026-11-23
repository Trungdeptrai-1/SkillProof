"""Backward-compatible alias for the server user model."""

import sys

from server.models import user_model as _implementation
from server.models.user_model import ROLE_ICONS, ROLE_LABELS, UserModel, UserRole

__all__ = ["ROLE_ICONS", "ROLE_LABELS", "UserModel", "UserRole"]

sys.modules[__name__] = _implementation
