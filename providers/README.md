# Custom LiteLLM Providers

This feature allows you to add custom model providers via YAML configuration files.

## Usage

1. Create a new YAML file in the `providers/` directory using `template.yaml` as a reference
2. Load your provider:

```python
from providers.loader import CustomProviderLoader

loader = CustomProviderLoader()
config = loader.load_provider("my_provider.yaml")
```

3. Use the loaded configuration with LiteLLM:

```python
import litellm

response = litellm.completion(
    model=config['model_name'],
    messages=[...],
    api_base=config['api_base'],
    api_key=config['api_key']
)
```

## YAML Template

See `template.yaml` for all available configuration options.

## Best Practices

- Keep your API keys secure
- Use descriptive model names
- Test your configuration thoroughly
- Document any custom parameters in your YAML file