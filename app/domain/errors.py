class DomainError(Exception):
    """Recoverable validation / ingestion issue."""


class ParseError(DomainError):
    """Malformed export file or unexpected sheet layout."""
