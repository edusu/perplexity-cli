"""Exception hierarchy for the Perplexity CLI."""


class PerplexityError(Exception):
    """Base exception for all Perplexity CLI errors."""


class AuthenticationError(PerplexityError):
    """Raised when authentication fails or cookies are missing/expired."""


class ChatError(PerplexityError):
    """Raised when the chat API returns an error."""


class RateLimitError(PerplexityError):
    """Raised when the API rate limit is exceeded."""
