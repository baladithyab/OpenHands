class LLMResponseError(Exception):
    """Raised when there is an error in the LLM response."""

    pass


class LLMMalformedActionError(Exception):
    """Raised when an LLM action is malformed."""

    pass