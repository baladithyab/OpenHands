# AWS Bedrock Integration

OpenHands now supports AWS Bedrock models with full feature support including:
- Prompt caching
- Cross-region inferencing
- Guardrails
- Multiple authentication methods
- Streaming responses

## Supported Models

The following AWS Bedrock models are supported:

### Anthropic Claude Models
- `bedrock/anthropic.claude-3-sonnet-20240229-v1:0`
- `bedrock/anthropic.claude-3-haiku-20240307-v1:0`
- `bedrock/anthropic.claude-3-opus-20240229-v1:0`

### Amazon Titan Models
- `bedrock/amazon.titan-text-express-v1`
- `bedrock/amazon.titan-text-lite-v1`

## Configuration

You can configure AWS Bedrock in your TOML configuration file. Here are the available options:

```toml
[llm]
model = "bedrock/anthropic.claude-3-sonnet-20240229-v1:0"

# AWS Authentication (multiple options available)
aws_access_key_id = "your-access-key"              # Basic auth
aws_secret_access_key = "your-secret-key"
aws_session_token = "optional-session-token"        # For temporary credentials
aws_region_name = "us-west-2"                      # Required
aws_profile_name = "your-profile"                  # For SSO/credential profiles
aws_role_name = "your-role"                        # For STS-based auth
aws_session_name = "your-session"                  # For role assumption
aws_web_identity_token = "your-token"              # For OIDC auth

# Bedrock-specific settings
aws_bedrock_runtime_endpoint = "custom-endpoint"    # Optional custom endpoint
guardrail_config = {                               # Optional guardrails
    guardrailIdentifier = "your-guardrail-id",
    guardrailVersion = "DRAFT",
    trace = "disabled"
}
cross_region_target = "us"                         # For cross-region inferencing

# General LLM settings
temperature = 0.7
top_p = 0.9
caching_prompt = true                              # Enable prompt caching
```

## Authentication Methods

### Basic Authentication
```toml
aws_access_key_id = "your-access-key"
aws_secret_access_key = "your-secret-key"
aws_region_name = "us-west-2"
```

### SSO Authentication
```toml
aws_profile_name = "dev-profile"
aws_region_name = "us-west-2"
```

### Role-based Authentication
```toml
aws_role_name = "your-role"
aws_session_name = "your-session"
aws_region_name = "us-west-2"
```

## Features

### Prompt Caching

Enable prompt caching to improve response times and reduce costs:

```toml
caching_prompt = true
```

The caching configuration is automatically handled based on the model type. For Bedrock models, it uses the native Bedrock caching mechanism with a default TTL of 1 hour.

### Cross-region Inferencing

Enable cross-region inferencing by setting the target region:

```toml
model = "bedrock/us.anthropic.claude-3-sonnet-20240229-v1:0"  # Note the 'us.' prefix
cross_region_target = "us"
```

### Guardrails

Configure Bedrock guardrails to enforce content policies:

```toml
guardrail_config = { 
    guardrailIdentifier = "your-guardrail-id",
    guardrailVersion = "DRAFT",
    trace = "disabled"
}
```

## Error Handling

The integration includes comprehensive error handling for Bedrock-specific errors:

- `ThrottlingException`: Handled with exponential backoff
- `ValidationException`: Invalid request parameters
- `InternalServerException`: Bedrock service errors

## Examples

See the [examples/bedrock_config.toml](../examples/bedrock_config.toml) file for complete configuration examples.