"""Tests for AWS Bedrock integration."""

import json
import pytest
from unittest.mock import MagicMock, patch

from openhands.core.config import LLMConfig
from openhands.llm.providers.bedrock import BedrockClient, BedrockError


@pytest.fixture
def bedrock_config():
    """Create a test config for Bedrock."""
    return LLMConfig(
        model='bedrock/anthropic.claude-3-sonnet-20240229-v1:0',
        aws_access_key_id='test-key',
        aws_secret_access_key='test-secret',
        aws_region_name='us-west-2',
        caching_prompt=True
    )


@pytest.fixture
def mock_boto3_session():
    """Create a mock boto3 session."""
    with patch('boto3.Session') as mock_session:
        mock_client = MagicMock()
        mock_session.return_value.client.return_value = mock_client
        yield mock_client


def test_bedrock_client_initialization(bedrock_config):
    """Test BedrockClient initialization."""
    client = BedrockClient(bedrock_config)
    assert client.config == bedrock_config


def test_bedrock_completion(bedrock_config, mock_boto3_session):
    """Test BedrockClient completion with caching."""
    client = BedrockClient(bedrock_config)
    
    # Mock successful response
    mock_response = {
        'body': MagicMock(
            read=lambda: b'{"completion": "Test response", "stop_reason": "stop", "usage": {}}'
        )
    }
    mock_boto3_session.invoke_model.return_value = mock_response
    
    # Test completion
    result = client.create_completion('Test prompt')
    
    # Verify the request
    mock_boto3_session.invoke_model.assert_called_once()
    call_kwargs = mock_boto3_session.invoke_model.call_args[1]
    
    # Check model ID
    assert call_kwargs['modelId'] == 'anthropic.claude-3-sonnet-20240229-v1:0'
    
    # Check content type
    assert call_kwargs['contentType'] == 'application/json'
    assert call_kwargs['accept'] == 'application/json'
    
    # Verify response parsing
    assert result['completion'] == 'Test response'
    assert result['stop_reason'] == 'stop'
    assert 'usage' in result


def test_bedrock_streaming(bedrock_config, mock_boto3_session):
    """Test BedrockClient streaming."""
    client = BedrockClient(bedrock_config)
    
    # Mock streaming response
    mock_chunk = {
        'chunk': {
            'bytes': b'{"completion": "Test chunk", "stop_reason": null, "usage": {}}'
        }
    }
    mock_boto3_session.invoke_model_with_response_stream.return_value = {
        'body': [mock_chunk]
    }
    
    # Test streaming
    chunks = list(client.create_completion('Test prompt', stream=True))
    
    # Verify streaming request
    mock_boto3_session.invoke_model_with_response_stream.assert_called_once()
    
    # Check streaming response
    assert len(chunks) == 1
    assert chunks[0]['completion'] == 'Test chunk'


def test_bedrock_error_handling(bedrock_config, mock_boto3_session):
    """Test BedrockClient error handling."""
    client = BedrockClient(bedrock_config)
    
    # Mock throttling error
    mock_boto3_session.invoke_model.side_effect = Exception('ThrottlingException')
    
    # Test error handling
    with pytest.raises(BedrockError) as exc_info:
        client.create_completion('Test prompt')
    
    assert 'ThrottlingException' in str(exc_info.value)


def test_bedrock_caching(bedrock_config, mock_boto3_session):
    """Test BedrockClient caching configuration."""
    client = BedrockClient(bedrock_config)
    
    # Mock successful response
    mock_response = {
        'body': MagicMock(
            read=lambda: b'{"completion": "Test response", "stop_reason": "stop", "usage": {}}'
        )
    }
    mock_boto3_session.invoke_model.return_value = mock_response
    
    # Test completion with caching
    client.create_completion('Test prompt')
    
    # Verify caching config in request
    call_kwargs = mock_boto3_session.invoke_model.call_args[1]
    request_body = json.loads(call_kwargs['body'])  # Convert string to dict
    assert 'cacheConfig' in request_body
    assert request_body['cacheConfig']['enabled'] is True
    assert request_body['cacheConfig']['ttl'] == 3600  # Default 1 hour