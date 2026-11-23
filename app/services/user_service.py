"""Backward-compatible imports for user registration operations."""

from server.services.user_service import RegisterResult, UserService, user_service

__all__ = ["RegisterResult", "UserService", "user_service"]
