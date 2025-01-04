import pytest
from providers.loader import CustomProviderLoader, ProviderConfig
from pathlib import Path
import yaml
import litellm

@pytest.fixture
def temp_provider_dir(tmp_path):
    return tmp_path

@pytest.fixture
def valid_provider_config(tmp_path):
    config = {
        "model_name": "test-model",
        "api_base": "https://api.example.com",
        "api_key": "test-key",
        "auth_type": "bearer",
        "timeout": 30,
        "params": {
            "temperature": 0.7
        }
    }
    # Create the providers directory
    providers_dir = tmp_path / "providers"
    providers_dir.mkdir()
    
    # Create the config file in the providers directory
    config_path = providers_dir / "test_provider.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config, f)
    return config_path

def test_load_valid_provider(temp_provider_dir, valid_provider_config):
    loader = CustomProviderLoader(providers_dir=temp_provider_dir)
    config = loader.load_provider(str(valid_provider_config))
    
    assert config["model_name"] == "test-model"
    assert config["api_base"] == "https://api.example.com"
    assert config["api_key"] == "test-key"
    assert config["auth_type"] == "bearer"
    assert config["timeout"] == 30
    assert config["params"]["temperature"] == 0.7

def test_missing_required_fields(temp_provider_dir, valid_provider_config):
    loader = CustomProviderLoader(providers_dir=temp_provider_dir)
    
    # Remove required field from config
    with open(valid_provider_config, "r") as f:
        config = yaml.safe_load(f)
    del config["api_key"]
    
    with open(valid_provider_config, "w") as f:
        yaml.dump(config, f)
    
    with pytest.raises(ValueError) as exc_info:
        loader.load_provider(valid_provider_config.name)
    assert "Missing required field: api_key" in str(exc_info.value)

def test_custom_provider_registration(temp_provider_dir, valid_provider_config):
    loader = CustomProviderLoader(providers_dir=temp_provider_dir)
    
    # Add custom provider class to config
    with open(valid_provider_config, "r") as f:
        config = yaml.safe_load(f)
    config["provider_class"] = "tests.fixtures.custom_provider.CustomProvider"
    
    with open(valid_provider_config, "w") as f:
        yaml.dump(config, f)
    
    # Test registration
    config = loader.load_provider(valid_provider_config.name)
    assert "test-model" in loader.list_models()
    assert litellm.get_provider("test-model") is not None

def test_invalid_provider_class(temp_provider_dir, valid_provider_config):
    loader = CustomProviderLoader(providers_dir=temp_provider_dir)
    
    # Add invalid provider class to config
    with open(valid_provider_config, "r") as f:
        config = yaml.safe_load(f)
    config["provider_class"] = "invalid.module.Class"
    
    with open(valid_provider_config, "w") as f:
        yaml.dump(config, f)
    
    with pytest.raises(ValueError) as exc_info:
        loader.load_provider(valid_provider_config.name)
    assert "Failed to register custom provider" in str(exc_info.value)

def test_litellm_integration(temp_provider_dir, valid_provider_config, mocker):
    loader = CustomProviderLoader(providers_dir=temp_provider_dir)
    config = loader.load_provider(valid_provider_config.name)
    
    # Mock litellm completion
    mock_response = {"choices": [{"message": {"content": "test response"}}]}
    mocker.patch("litellm.completion", return_value=mock_response)
    
    response = litellm.completion(
        model=config["model_name"],
        messages=[{"role": "user", "content": "test"}],
        **config["params"]
    )
    
    assert response["choices"][0]["message"]["content"] == "test response"