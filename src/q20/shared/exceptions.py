"""Project exception hierarchy.

A single base (``Q20Error``) lets callers catch everything from this project with
one ``except``, while specific subclasses carry precise meaning.
"""


class Q20Error(Exception):
    """Base class for all project-specific errors."""


class ConfigError(Q20Error):
    """A configuration file is missing, malformed, or internally inconsistent."""


class VersionMismatchError(ConfigError):
    """A config file's declared version disagrees with the code version."""


class RateLimitExceededError(Q20Error):
    """The gatekeeper's configured rate limit was exceeded and could not recover."""


class CostCapExceededError(Q20Error):
    """Cumulative spend for a run exceeded the configured cap (cloud engines only)."""


class CorpusError(Q20Error):
    """The corpus source is missing, empty, or malformed."""


class AgentStepError(Q20Error):
    """An agent produced output that failed validation against its contract."""
