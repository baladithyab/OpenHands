import pytest

from openhands.core.exceptions.token_errors import TokenLimitError


def test_token_limit_error_basic():
    error = TokenLimitError("Test error message")
    assert str(error) == "Test error message"
    assert error.input_tokens is None
    assert error.max_input_tokens is None
    assert error.output_tokens is None
    assert error.max_output_tokens is None


def test_token_limit_error_with_input_tokens():
    error = TokenLimitError(
        "Input tokens exceed limit",
        input_tokens=5000,
        max_input_tokens=4096,
    )
    assert str(error) == "Input tokens exceed limit"
    assert error.input_tokens == 5000
    assert error.max_input_tokens == 4096
    assert error.output_tokens is None
    assert error.max_output_tokens is None


def test_token_limit_error_with_output_tokens():
    error = TokenLimitError(
        "Output tokens exceed limit",
        output_tokens=2000,
        max_output_tokens=1000,
    )
    assert str(error) == "Output tokens exceed limit"
    assert error.input_tokens is None
    assert error.max_input_tokens is None
    assert error.output_tokens == 2000
    assert error.max_output_tokens == 1000


def test_token_limit_error_with_all_tokens():
    error = TokenLimitError(
        "Both input and output tokens exceed limits",
        input_tokens=5000,
        max_input_tokens=4096,
        output_tokens=2000,
        max_output_tokens=1000,
    )
    assert str(error) == "Both input and output tokens exceed limits"
    assert error.input_tokens == 5000
    assert error.max_input_tokens == 4096
    assert error.output_tokens == 2000
    assert error.max_output_tokens == 1000