"""Custom exceptions for ForgeKit."""


class ForgeKitError(Exception):
    """Base exception for ForgeKit."""

    def __init__(self, message: str, exit_code: int = 1) -> None:
        super().__init__(message)
        self.exit_code = exit_code


class ConfigError(ForgeKitError):
    """Configuration related error."""


class PlatformNotSupportedError(ForgeKitError):
    """Raised when a feature is not supported on current platform."""


class PermissionDeniedError(ForgeKitError):
    """Raised when operation needs elevated permissions."""


class BackupError(ForgeKitError):
    """Backup operation error."""


class NetworkError(ForgeKitError):
    """Network operation error."""


class GitError(ForgeKitError):
    """Git operation error."""
