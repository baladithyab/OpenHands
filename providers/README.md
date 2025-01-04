# Enhanced Custom LiteLLM Providers

This feature allows dynamic registration of custom model providers and configurations via YAML files.

## Key Features
- Dynamic provider registration
- Custom authentication schemes
- Schema validation
- Provider-specific parameters
- Custom provider classes
- Built-in validation rules

## Usage

1. Create a new YAML file in the `providers/` directory using `template.yaml` as a reference
2. Load and register your provider:

```python
from providers.loader import CustomProviderLoader

loader = CustomProviderLoader()
config = loader.load_provider("my_provider.yaml")
```

3. Use the provider with LiteLLM:

```python
import litellm

response = litellm.completion(
    model=config['model_name'],
    messages=[{"role": "user", "content": "Hello"}],
    **config['params']
)
```

## Advanced Usage

### Custom Provider Classes
```yaml
provider_class: "my_module.CustomProvider"
```

### Custom Authentication
```yaml
auth_type: "basic"  # or "bearer", "none"
custom_headers:
  Authorization: "Basic <credentials>"
```

### Validation Rules
```yaml
validation:
  required_fields: ["model_name", "api_base"]
  allowed_auth_types: ["bearer", "basic"]
  min_timeout: 10
```

## Best Practices
- Use environment variables for sensitive data
- Validate configurations before deployment
- Document custom parameters
- Test with different authentication schemes
- Monitor provider performance