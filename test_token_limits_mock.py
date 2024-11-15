import sys
import unittest
from unittest.mock import patch, MagicMock

from litellm import APIError
from litellm.types.utils import ModelResponse

from openhands.core.config import LLMConfig
from openhands.core.exceptions.token_errors import TokenLimitError

# Mock litellm before importing LLM
with patch.dict('sys.modules', {'litellm': MagicMock()}) as mock_modules:
    from openhands.llm.llm import LLM

def create_long_message(length: int) -> str:
    # Create a message of approximately the specified length
    # Each word is about 5 characters, so divide by 6 (including space)
    words = ["hello"] * (length // 6)
    return " ".join(words)

class TestTokenLimits(unittest.TestCase):
    def setUp(self):
        self.config = LLMConfig(
            model="gpt-3.5-turbo",
            api_key="test-key",  # Dummy key for testing
            max_input_tokens=1000,  # Small limit for testing
            max_output_tokens=100,
            num_retries=0,  # Disable retries for testing
        )
        
        self.llm = LLM(self.config)
        
        # Mock litellm completion to avoid API calls
        self.completion_patcher = patch.object(self.llm, '_completion_unwrapped')
        self.mock_completion = self.completion_patcher.start()
        
        # Set up litellm mock
        self.mock_litellm = sys.modules['litellm']
        
    def tearDown(self):
        self.completion_patcher.stop()
        self.mock_litellm.reset_mock()

    def create_mock_response(self, content: str) -> MagicMock:
        mock_response = MagicMock(spec=ModelResponse)
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message = {"content": content}
        return mock_response

    def test_message_within_limits(self):
        """Test that a message within token limits is processed successfully"""
        self.mock_litellm.token_counter.return_value = 500
        self.mock_completion.return_value = self.create_mock_response("Test response")
        
        messages = [{
            "role": "user", 
            "content": create_long_message(100)
        }]
        response = self.llm.completion(messages=messages)
        
        self.assertEqual(response.choices[0].message["content"], "Test response")
        self.mock_completion.assert_called_once()
        self.mock_litellm.token_counter.assert_called_once_with(model=self.config.model, messages=messages)

    def test_message_exceeding_limits(self):
        """Test that a message exceeding token limits raises TokenLimitError"""
        self.mock_litellm.token_counter.return_value = 1500
        self.mock_completion.return_value = self.create_mock_response("Should not reach here")
        
        messages = [{
            "role": "user", 
            "content": create_long_message(10000)
        }]
        with self.assertRaises(TokenLimitError) as context:
            self.llm.completion(messages=messages)
        
        self.assertEqual(context.exception.input_tokens, 1500)
        self.assertEqual(context.exception.max_input_tokens, 1000)
        self.mock_completion.assert_not_called()
        self.mock_litellm.token_counter.assert_called_once_with(model=self.config.model, messages=messages)

    def test_api_token_limit_error(self):
        """Test that token limit errors from the API are handled correctly"""
        self.mock_litellm.token_counter.return_value = 500
        self.mock_completion.side_effect = APIError(
            message="Maximum context length exceeded",
            llm_provider="test",
            model="test",
            status_code=400,
        )
        
        messages = [{
            "role": "user", 
            "content": create_long_message(1000)
        }]
        with self.assertRaises(TokenLimitError) as context:
            self.llm.completion(messages=messages)
        
        self.assertIn("Maximum context length exceeded", str(context.exception))
        self.mock_litellm.token_counter.assert_called_once_with(model=self.config.model, messages=messages)

    def test_multiple_messages_token_accumulation(self):
        """Test that multiple messages' tokens are accumulated correctly"""
        self.mock_litellm.token_counter.return_value = 1200
        self.mock_completion.return_value = self.create_mock_response("Should not reach here")
        
        messages = [
            {"role": "user", "content": create_long_message(500)},
            {"role": "assistant", "content": create_long_message(500)},
            {"role": "user", "content": create_long_message(500)}
        ]
        
        with self.assertRaises(TokenLimitError) as context:
            self.llm.completion(messages=messages)
        
        self.assertEqual(context.exception.input_tokens, 1200)
        self.assertEqual(context.exception.max_input_tokens, 1000)
        self.mock_completion.assert_not_called()
        self.mock_litellm.token_counter.assert_called_once_with(model=self.config.model, messages=messages)

if __name__ == '__main__':
    unittest.main(verbosity=2)