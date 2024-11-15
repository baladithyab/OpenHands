import asyncio
from openhands.core.config import LLMConfig
from openhands.llm.llm import LLM
from openhands.core.exceptions.token_errors import TokenLimitError

def create_long_message(length: int) -> str:
    # Create a message of approximately the specified length
    # Each word is about 5 characters, so divide by 6 (including space)
    words = ["hello"] * (length // 6)
    return " ".join(words)

async def test_token_limits():
    print("\nTesting token limit handling...")
    
    # Initialize LLM with a small token limit for testing
    config = LLMConfig(
        model="gpt-3.5-turbo",
        max_input_tokens=1000,  # Small limit for testing
        max_output_tokens=100,
    )
    llm = LLM(config)

    # Test 1: Message within limits
    print("\nTest 1: Message within token limits")
    try:
        short_msg = create_long_message(100)
        response = llm.completion(messages=[{"role": "user", "content": short_msg}])
        print("✓ Successfully processed message within limits")
        print(f"Response: {response.choices[0].message['content'][:100]}...")
    except Exception as e:
        print(f"✗ Unexpected error with short message: {e}")

    # Test 2: Message exceeding token limit
    print("\nTest 2: Message exceeding token limits")
    try:
        long_msg = create_long_message(10000)
        response = llm.completion(messages=[{"role": "user", "content": long_msg}])
        print("✗ Expected TokenLimitError but got response")
    except TokenLimitError as e:
        print(f"✓ Successfully caught TokenLimitError: {e}")
        print(f"Input tokens: {e.input_tokens}")
        print(f"Max input tokens: {e.max_input_tokens}")
    except Exception as e:
        print(f"✗ Unexpected error type: {e}")

    # Test 3: Multiple messages accumulating tokens
    print("\nTest 3: Multiple messages accumulating tokens")
    try:
        messages = [
            {"role": "user", "content": create_long_message(2000)},
            {"role": "assistant", "content": create_long_message(2000)},
            {"role": "user", "content": create_long_message(2000)}
        ]
        response = llm.completion(messages=messages)
        print("✗ Expected TokenLimitError but got response")
    except TokenLimitError as e:
        print(f"✓ Successfully caught TokenLimitError: {e}")
    except Exception as e:
        print(f"✗ Unexpected error type: {e}")

if __name__ == "__main__":
    asyncio.run(test_token_limits())