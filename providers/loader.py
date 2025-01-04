import yaml
import litellm
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseModel, ValidationError
import importlib

class ProviderConfig(BaseModel):
    model_name: str
    api_base: str
    api_key: str
    provider_class: Optional[str] = None
    auth_type: str = "bearer"
    custom_headers: Dict[str, str] = {}
    params: Dict[str, Any] = {}
    timeout: int = 30
    max_retries: int = 3
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    stream: bool = False

class CustomProviderLoader:
    def __init__(self, providers_dir: str = "providers"):
        self.providers_dir = Path(providers_dir)
        self.providers_dir.mkdir(exist_ok=True)
        self.loaded_models: Dict[str, Any] = {}

    def load_provider(self, yaml_path: str) -> Dict[str, Any]:
        """Load and validate a provider YAML file"""
        # Handle both direct paths and paths relative to providers_dir
        path = Path(yaml_path)
        if not path.is_absolute():
            path = self.providers_dir / yaml_path
        if not path.exists():
            raise FileNotFoundError(f"Provider file {path} not found")
            
        with open(path, 'r') as f:
            config = yaml.safe_load(f)
            
        try:
            validated_config = ProviderConfig(**config).dict()
        except ValidationError as e:
            raise ValueError(f"Invalid provider configuration: {e}")

        # Register custom provider if specified
        if validated_config.get('provider_class'):
            self._register_custom_provider(validated_config)

        # Register with LiteLLM
        litellm.register_provider(
            model_name=validated_config['model_name'],
            provider_config=validated_config
        )

        self.loaded_models[validated_config['model_name']] = validated_config
        return validated_config

    def _register_custom_provider(self, config: Dict[str, Any]) -> None:
        """Dynamically load and register custom provider class"""
        try:
            module_path, class_name = config['provider_class'].rsplit('.', 1)
            module = importlib.import_module(module_path)
            provider_class = getattr(module, class_name)
            litellm.register_provider_class(
                provider_name=config['model_name'],
                provider_class=provider_class
            )
        except Exception as e:
            raise ValueError(f"Failed to register custom provider: {e}")

    def get_model_config(self, model_name: str) -> Dict[str, Any]:
        """Get configuration for a loaded model"""
        return self.loaded_models.get(model_name)

    def list_models(self) -> Dict[str, Any]:
        """List all loaded models"""
        return self.loaded_models