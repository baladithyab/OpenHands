"""AWS Bedrock integration for OpenHands."""

import json
import time
from functools import wraps
from typing import Any, Dict, Iterator, Optional

import boto3
from botocore.exceptions import ClientError

from openhands.core.config import LLMConfig
from openhands.core.logger import openhands_logger as logger


class BedrockError(Exception):
    """Base exception for Bedrock-related errors."""
    pass


class BedrockClient:
    """Client for AWS Bedrock service with proper error handling and caching."""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.client = self._initialize_client()
        
    def _initialize_client(self) -> Any:
        """Initialize the Bedrock client with proper configuration."""
        try:
            session_kwargs = {
                'region_name': self.config.aws_region_name
            }
            
            # Add optional authentication parameters
            if self.config.aws_access_key_id and self.config.aws_secret_access_key:
                session_kwargs.update({
                    'aws_access_key_id': self.config.aws_access_key_id,
                    'aws_secret_access_key': self.config.aws_secret_access_key
                })
                if self.config.aws_session_token:
                    session_kwargs['aws_session_token'] = self.config.aws_session_token
            elif self.config.aws_profile_name:
                session_kwargs['profile_name'] = self.config.aws_profile_name
                
            session = boto3.Session(**session_kwargs)
            
            client_kwargs = {
                'service_name': 'bedrock-runtime',
                'region_name': self.config.aws_region_name,
            }
            
            if self.config.aws_bedrock_runtime_endpoint:
                client_kwargs['endpoint_url'] = self.config.aws_bedrock_runtime_endpoint
                
            return session.client(**client_kwargs)
            
        except Exception as e:
            raise BedrockError(f"Failed to initialize Bedrock client: {str(e)}")
    
    def _handle_bedrock_error(func):
        """Decorator for handling Bedrock API errors with retries."""
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            retries = 0
            max_retries = self.config.num_retries or 3
            while retries < max_retries:
                try:
                    return func(self, *args, **kwargs)
                except ClientError as e:
                    error_code = e.response['Error']['Code']
                    if error_code == 'ValidationException':
                        raise BedrockError(f"Invalid request: {str(e)}")
                    elif error_code == 'ThrottlingException':
                        retries += 1
                        if retries == max_retries:
                            raise BedrockError(f"Rate limit exceeded after {max_retries} retries")
                        wait_time = min(
                            self.config.retry_max_wait,
                            self.config.retry_min_wait * (self.config.retry_multiplier ** retries)
                        )
                        time.sleep(wait_time)
                    elif error_code == 'InternalServerException':
                        raise BedrockError(f"Bedrock internal error: {str(e)}")
                    else:
                        raise BedrockError(f"Unexpected Bedrock error: {str(e)}")
                except Exception as e:
                    raise BedrockError(f"Error during Bedrock API call: {str(e)}")
        return wrapper

    def _prepare_model_kwargs(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Prepare model-specific kwargs based on the model ID."""
        model_id = self.config.model.replace('bedrock/', '')
        
        # Base parameters
        params = {
            'temperature': kwargs.get('temperature', self.config.temperature),
            'top_p': kwargs.get('top_p', self.config.top_p),
            'max_tokens': kwargs.get('max_tokens', self.config.max_output_tokens),
        }
        
        # Model-specific formatting
        if model_id.startswith('anthropic.claude'):
            return {
                'prompt': f'Human: {prompt}\n\nAssistant:',
                'temperature': params['temperature'],
                'top_p': params['top_p'],
                'max_tokens': params['max_tokens'],
                'anthropic_version': 'bedrock-2023-05-31'
            }
        elif model_id.startswith('amazon.titan'):
            return {
                'inputText': prompt,
                'textGenerationConfig': {
                    'temperature': params['temperature'],
                    'topP': params['top_p'],
                    'maxTokenCount': params['max_tokens']
                }
            }
        elif model_id.startswith('ai21'):
            return {
                'prompt': prompt,
                'temperature': params['temperature'],
                'topP': params['top_p'],
                'maxTokens': params['max_tokens']
            }
        else:
            raise BedrockError(f"Unsupported model: {model_id}")

    @_handle_bedrock_error
    def create_completion(
        self,
        prompt: str,
        stream: bool = False,
        **kwargs
    ) -> Dict[str, Any] | Iterator[Dict[str, Any]]:
        """Create a completion using AWS Bedrock with proper caching."""
        model_id = self.config.model.replace('bedrock/', '')
        request_body = self._prepare_model_kwargs(prompt, **kwargs)
        
        # Add caching if enabled
        if self.config.caching_prompt:
            request_body['cacheConfig'] = {
                'enabled': True,
                'ttl': kwargs.get('cache_ttl', 3600)  # 1 hour default
            }
            
        # Add guardrails if configured
        if self.config.guardrail_config:
            request_body['guardrailConfig'] = self.config.guardrail_config
            
        if stream:
            return self._stream_completion(model_id, request_body)
        else:
            return self._sync_completion(model_id, request_body)
            
    def _sync_completion(self, model_id: str, request_body: Dict[str, Any]) -> Dict[str, Any]:
        """Make a synchronous completion request."""
        response = self.client.invoke_model(
            modelId=model_id,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(request_body)
        )
        
        response_body = json.loads(response.get('body').read())
        
        # Extract completion based on model type
        if model_id.startswith('anthropic.claude'):
            return {
                'completion': response_body.get('completion', ''),
                'stop_reason': response_body.get('stop_reason'),
                'usage': response_body.get('usage', {})
            }
        elif model_id.startswith('amazon.titan'):
            return {
                'completion': response_body.get('results', [{}])[0].get('outputText', ''),
                'usage': response_body.get('inputTokenCount', {}),
            }
        elif model_id.startswith('ai21'):
            return {
                'completion': response_body.get('completions', [{}])[0].get('data', {}).get('text', ''),
                'usage': response_body.get('usage', {})
            }
        else:
            raise BedrockError(f"Unsupported model response format: {model_id}")
            
    def _stream_completion(
        self,
        model_id: str,
        request_body: Dict[str, Any]
    ) -> Iterator[Dict[str, Any]]:
        """Stream completion responses."""
        response = self.client.invoke_model_with_response_stream(
            modelId=model_id,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(request_body)
        )
        
        for event in response.get('body'):
            if event:
                chunk = json.loads(event.get('chunk').get('bytes').decode())
                
                # Extract streaming chunk based on model type
                if model_id.startswith('anthropic.claude'):
                    yield {
                        'completion': chunk.get('completion', ''),
                        'stop_reason': chunk.get('stop_reason'),
                        'usage': chunk.get('usage', {})
                    }
                elif model_id.startswith('amazon.titan'):
                    yield {
                        'completion': chunk.get('outputText', ''),
                        'usage': chunk.get('inputTokenCount', {})
                    }
                elif model_id.startswith('ai21'):
                    yield {
                        'completion': chunk.get('completions', [{}])[0].get('data', {}).get('text', ''),
                        'usage': chunk.get('usage', {})
                    }
                    
    def list_models(self) -> list[str]:
        """List available foundation models."""
        try:
            # Use bedrock (not bedrock-runtime) for listing models
            bedrock_client = self.client._client_config.client_name.replace(
                'bedrock-runtime', 'bedrock'
            )
            client = boto3.client(
                service_name=bedrock_client,
                region_name=self.config.aws_region_name
            )
            
            response = client.list_foundation_models(
                byOutputModality='TEXT',
                byInferenceType='ON_DEMAND'
            )
            
            return ['bedrock/' + model['modelId'] for model in response['modelSummaries']]
            
        except Exception as e:
            logger.warning(
                'Failed to list Bedrock models: %s. Please check AWS credentials and permissions.',
                str(e)
            )
            return []