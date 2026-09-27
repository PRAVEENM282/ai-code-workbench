class UpstreamProviderError(Exception):
    """An LLM provider failed after bounded retries."""


class ConfigurationError(Exception):
    """Runtime configuration is invalid or incomplete."""
