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


class AgentError(DomainError):
    """Base error for AI pipeline agents."""

    code: str = "agent_error"

    def __init__(self, message: str, *, agent: str | None = None):
        self.agent = agent
        super().__init__(message)


class AgentValidationError(AgentError):
    code = "agent_validation_error"

    def __init__(
        self,
        message: str,
        *,
        agent: str | None = None,
        errors: list[dict] | None = None,
    ):
        self.errors = errors or []
        super().__init__(message, agent=agent)


class AgentInputError(AgentError):
    code = "agent_input_error"


class AgentOutputParseError(AgentError):
    code = "agent_output_parse_error"


class AgentUpstreamError(AgentError):
    code = "agent_upstream_error"


class AgentRateLimitError(AgentError):
    code = "agent_rate_limited"


class IdempotencyConflict(DomainError):
    """Same idempotency key, different payload hash."""
