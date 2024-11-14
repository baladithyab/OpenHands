import pytest
from unittest.mock import MagicMock, patch

from litellm import APIError
from litellm.types.utils import ModelResponse

from openhands.core.config import AgentConfig, LLMConfig
from openhands.core.exceptions.token_errors import TokenLimitError
from openhands.llm.llm import LLM
from openhands.llm.metrics import Metrics


@pytest.fixture
def llm_config():
    return LLMConfig(
        model="gpt-4",
        api_key="test-key",
        max_input_tokens=4096,
        max_output_tokens=1000,
    )


@pytest.fixture
def llm(llm_config):
    return LLM(llm_config)


def test_token_limit_validation(llm):
    with patch.object(llm, 'get_token_count', return_value=5000):
        with patch('litellm.completion') as mock_completion:
            with patch('litellm.llms.OpenAI.openai.OpenAIChatCompletion._get_openai_client') as mock_client:
                mock_response = MagicMock(spec=ModelResponse)
                mock_response.choices = [MagicMock()]
                mock_response.choices[0].message = {"content": "test response"}
                mock_completion.return_value = mock_response
                
                with pytest.raises(TokenLimitError) as exc_info:
                    llm.completion(messages=[{"role": "user", "content": "test"}])
                
                assert exc_info.value.input_tokens == 5000
                assert exc_info.value.max_input_tokens == 4096
                mock_completion.assert_not_called()
                mock_client.assert_not_called()


def test_token_limit_api_error(llm):
    with patch.object(llm, 'get_token_count', return_value=2000):
        with patch('litellm.completion') as mock_completion:
            with patch('litellm.llms.OpenAI.openai.OpenAIChatCompletion._get_openai_client') as mock_client:
                mock_response = MagicMock(spec=ModelResponse)
                mock_response.choices = [MagicMock()]
                mock_response.choices[0].message = {"content": "test response"}
                mock_completion.side_effect = APIError(
                    message="Maximum context length exceeded",
                    llm_provider="test",
                    model="test",
                    status_code=400,
                )
                
                with pytest.raises(TokenLimitError) as exc_info:
                    llm.completion(messages=[{"role": "user", "content": "test"}])
                
                assert "Maximum context length exceeded" in str(exc_info.value)


def test_token_limit_retry(llm):
    with patch.object(llm, 'get_token_count', return_value=2000):
        with patch('litellm.completion') as mock_completion:
            with patch('litellm.llms.OpenAI.openai.OpenAIChatCompletion._get_openai_client') as mock_client:
                # First call raises token limit error, second call succeeds
                mock_response = MagicMock(spec=ModelResponse)
                mock_response.choices = [MagicMock()]
                mock_response.choices[0].message = {"content": "test response"}
                mock_completion.side_effect = [
                    APIError(
                        message="Maximum context length exceeded",
                        llm_provider="test",
                        model="test",
                        status_code=400,
                    ),
                    mock_response
                ]
                
                # Should not raise and return the mock response
                response = llm.completion(messages=[{"role": "user", "content": "test"}])
                assert response.choices[0].message["content"] == "test response"
                assert mock_completion.call_count == 2


def test_non_token_api_error(llm):
    with patch.object(llm, 'get_token_count', return_value=2000):
        with patch('litellm.completion') as mock_completion:
            with patch('litellm.llms.OpenAI.openai.OpenAIChatCompletion._get_openai_client') as mock_client:
                mock_response = MagicMock(spec=ModelResponse)
                mock_response.choices = [MagicMock()]
                mock_response.choices[0].message = {"content": "test response"}
                mock_completion.side_effect = APIError(
                    message="Other API error",
                    llm_provider="test",
                    model="test",
                    status_code=500,
                )
                
                with pytest.raises(APIError) as exc_info:
                    llm.completion(messages=[{"role": "user", "content": "test"}])
                
                assert "Other API error" in str(exc_info.value)


def test_token_count_failure_continues(llm):
    with patch.object(llm, 'get_token_count', side_effect=Exception("Token count failed")):
        with patch('litellm.completion') as mock_completion:
            with patch('litellm.llms.OpenAI.openai.OpenAIChatCompletion._get_openai_client') as mock_client:
                mock_response = MagicMock(spec=ModelResponse)
                mock_response.choices = [MagicMock()]
                mock_response.choices[0].message = {"content": "test response"}
                mock_completion.return_value = mock_response
                
                # Should not raise and return the mock response
                response = llm.completion(messages=[{"role": "user", "content": "test"}])
                assert response.choices[0].message["content"] == "test response"