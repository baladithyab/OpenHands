class CloudFlareBlockageError(Exception):
    """Raised when a request is blocked by CloudFlare."""

    pass


class AgentAlreadyRegisteredError(Exception):
    """Raised when attempting to register an agent that is already registered."""

    pass


class AgentNotRegisteredError(Exception):
    """Raised when attempting to use an agent that is not registered."""

    pass