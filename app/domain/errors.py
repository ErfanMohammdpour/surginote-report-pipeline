class DomainError(Exception):
    """Recoverable validation / ingestion issue."""


class ParseError(DomainError):
    """Malformed export file or unexpected sheet layout."""


class ValidationError(DomainError):
    def __init__(self, errors: list[dict]):
        self.errors = errors
        super().__init__(f"validation failed: {len(errors)} error(s)")


class StorageError(DomainError):
    """Object storage failure."""


class UploadError(DomainError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


class IdempotencyConflict(DomainError):
    """Same idempotency key, different payload hash."""
