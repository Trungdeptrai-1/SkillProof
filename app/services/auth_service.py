"""Backward-compatible imports for the authentication service."""

from server.services.auth_service import (
    AuthService,
    LoginResult,
    SessionManager,
    auth_service,
    session,
)

__all__ = [
    "AuthService",
    "LoginResult",
    "SessionManager",
    "auth_service",
    "session",
]
