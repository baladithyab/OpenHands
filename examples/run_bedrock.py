"""Example script to run AWS Bedrock models."""

import os
from openhands.core.config import LLMConfig
from openhands.llm.providers.bedrock import BedrockClient

def main():
    # Load AWS credentials from environment variables
    aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
    aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    aws_region_name = os.getenv('AWS_REGION_NAME', 'us-west-2')

    if not aws_access_key_id or not aws_secret_access_key:
        print("Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables")
        return

    # Create config for Bedrock
    config = LLMConfig(
        model='bedrock/anthropic.claude-3-sonnet-20240229-v1:0',
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        aws_region_name=aws_region_name,
        caching_prompt=True
    )

    # Create Bedrock client
    client = BedrockClient(config)
    print("Successfully created Bedrock client")

    # Test a simple completion
    prompt = "What is the capital of France? Please answer in one word."
    print("\nSending prompt:", prompt)
    
    try:
        response = client.create_completion(prompt)
        print("\nResponse:", response['completion'])
    except Exception as e:
        print("\nError:", str(e))

    # Test streaming
    prompt = "Count from 1 to 5, one number per line."
    print("\nTesting streaming with prompt:", prompt)
    
    try:
        print("\nStreaming response:")
        for chunk in client.create_completion(prompt, stream=True):
            print(chunk['completion'], end='', flush=True)
        print()  # New line after streaming
    except Exception as e:
        print("\nError:", str(e))

if __name__ == '__main__':
    main()