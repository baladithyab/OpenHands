from typing import Optional


class TokenLimitError(Exception):
    """Raised when the input or output tokens exceed the model's limits."""

    def __init__(
        self,
        message: str,
        input_tokens: Optional[int] = None,
        max_input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        max_output_tokens: Optional[int] = None,
    ):
        self.input_tokens = input_tokens
        self.max_input_tokens = max_input_tokens
        self.output_tokens = output_tokens
        self.max_output_tokens = max_output_tokens
        super().__init__(message)