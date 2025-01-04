import yaml
from pathlib import Path
from typing import Dict, Any

class CustomProviderLoader:
    def __init__(self, providers_dir: str = "providers"):
        self.providers_dir = Path(providers_dir)
        self.providers_dir.mkdir(exist_ok=True)
        self.loaded_models: Dict[str, Any] = {}

    def load_provider(self, yaml_path: str) -> Dict[str, Any]:
        """Load and validate a provider YAML file"""
        path = self.providers_dir / yaml_path
        if not path.exists():
            raise FileNotFoundError(f"Provider file {path} not found")
            
        with open(path, 'r') as f:
            config = yaml.safe_load(f)
            
        # Basic validation
        required_fields = ['model_name', 'api_base', 'api_key']
        for field in required_fields:
            if field not in config:
                raise ValueError(f"Missing required field: {field}")
                
        self.loaded_models[config['model_name']] = config
        return config

    def get_model_config(self, model_name: str) -> Dict[str, Any]:
        """Get configuration for a loaded model"""
        return self.loaded_models.get(model_name)

    def list_models(self) -> Dict[str, Any]:
        """List all loaded models"""
        return self.loaded_models