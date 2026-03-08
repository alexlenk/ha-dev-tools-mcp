"""Unit tests for configuration management."""

import os
import pytest
from ha_dev_tools.config import ConfigError, ServerConfig, load_config


class TestServerConfig:
    """Tests for ServerConfig dataclass."""
    
    def test_server_config_creation(self):
        """Test creating a ServerConfig instance."""
        config = ServerConfig(
            ha_url="http://homeassistant.local:8123",
            ha_token="test_token_123"
        )
        assert config.ha_url == "http://homeassistant.local:8123"
        assert config.ha_token == "test_token_123"
        assert config.request_timeout == 30  # Default value
    
    def test_server_config_custom_timeout(self):
        """Test creating a ServerConfig with custom timeout."""
        config = ServerConfig(
            ha_url="https://ha.example.com",
            ha_token="token",
            request_timeout=60
        )
        assert config.request_timeout == 60


class TestLoadConfig:
    """Tests for load_config function."""
    
    def test_load_config_success_http(self, monkeypatch):
        """Test loading valid configuration with http URL."""
        monkeypatch.setenv("HA_URL", "http://homeassistant.local:8123")
        monkeypatch.setenv("HA_TOKEN", "test_token_abc123")
        
        config = load_config()
        
        assert config.ha_url == "http://homeassistant.local:8123"
        assert config.ha_token == "test_token_abc123"
        assert config.request_timeout == 30
    
    def test_load_config_success_https(self, monkeypatch):
        """Test loading valid configuration with https URL."""
        monkeypatch.setenv("HA_URL", "https://ha.example.com")
        monkeypatch.setenv("HA_TOKEN", "secure_token_xyz")
        
        config = load_config()
        
        assert config.ha_url == "https://ha.example.com"
        assert config.ha_token == "secure_token_xyz"
    
    def test_load_config_missing_ha_url(self, monkeypatch):
        """Test that missing HA_URL raises ConfigError."""
        monkeypatch.delenv("HA_URL", raising=False)
        monkeypatch.setenv("HA_TOKEN", "test_token")
        
        with pytest.raises(ConfigError) as exc_info:
            load_config()
        
        assert "HA_URL environment variable is required" in str(exc_info.value)
    
    def test_load_config_missing_ha_token(self, monkeypatch):
        """Test that missing HA_TOKEN raises ConfigError."""
        monkeypatch.setenv("HA_URL", "http://homeassistant.local:8123")
        monkeypatch.delenv("HA_TOKEN", raising=False)
        
        with pytest.raises(ConfigError) as exc_info:
            load_config()
        
        assert "HA_TOKEN environment variable is required" in str(exc_info.value)
    
    def test_load_config_invalid_url_no_protocol(self, monkeypatch):
        """Test that URL without http:// or https:// raises ConfigError."""
        monkeypatch.setenv("HA_URL", "homeassistant.local:8123")
        monkeypatch.setenv("HA_TOKEN", "test_token")
        
        with pytest.raises(ConfigError) as exc_info:
            load_config()
        
        assert "HA_URL must start with http:// or https://" in str(exc_info.value)
    
    def test_load_config_invalid_url_wrong_protocol(self, monkeypatch):
        """Test that URL with wrong protocol raises ConfigError."""
        monkeypatch.setenv("HA_URL", "ftp://homeassistant.local:8123")
        monkeypatch.setenv("HA_TOKEN", "test_token")
        
        with pytest.raises(ConfigError) as exc_info:
            load_config()
        
        assert "HA_URL must start with http:// or https://" in str(exc_info.value)
    
    def test_load_config_empty_ha_url(self, monkeypatch):
        """Test that empty HA_URL raises ConfigError."""
        monkeypatch.setenv("HA_URL", "")
        monkeypatch.setenv("HA_TOKEN", "test_token")
        
        with pytest.raises(ConfigError) as exc_info:
            load_config()
        
        assert "HA_URL environment variable is required" in str(exc_info.value)
    
    def test_load_config_empty_ha_token(self, monkeypatch):
        """Test that empty HA_TOKEN raises ConfigError."""
        monkeypatch.setenv("HA_URL", "http://homeassistant.local:8123")
        monkeypatch.setenv("HA_TOKEN", "")
        
        with pytest.raises(ConfigError) as exc_info:
            load_config()
        
        assert "HA_TOKEN environment variable is required" in str(exc_info.value)
    
    def test_load_config_url_with_path(self, monkeypatch):
        """Test that URL with path is accepted."""
        monkeypatch.setenv("HA_URL", "https://ha.example.com/api")
        monkeypatch.setenv("HA_TOKEN", "test_token")
        
        config = load_config()
        
        assert config.ha_url == "https://ha.example.com/api"
    
    def test_load_config_url_with_port(self, monkeypatch):
        """Test that URL with custom port is accepted."""
        monkeypatch.setenv("HA_URL", "http://192.168.1.100:8123")
        monkeypatch.setenv("HA_TOKEN", "test_token")
        
        config = load_config()
        
        assert config.ha_url == "http://192.168.1.100:8123"


class TestMaxFileSizeConfig:
    """Tests for max_file_size configuration."""
    
    def test_default_max_file_size(self, monkeypatch):
        """Test that default max_file_size is 10MB."""
        monkeypatch.setenv("HA_URL", "http://homeassistant.local:8123")
        monkeypatch.setenv("HA_TOKEN", "test_token")
        monkeypatch.delenv("MAX_FILE_SIZE", raising=False)
        
        config = load_config()
        
        assert config.max_file_size == 10 * 1024 * 1024  # 10MB
    
    def test_custom_max_file_size(self, monkeypatch):
        """Test that custom max_file_size is respected."""
        monkeypatch.setenv("HA_URL", "http://homeassistant.local:8123")
        monkeypatch.setenv("HA_TOKEN", "test_token")
        monkeypatch.setenv("MAX_FILE_SIZE", str(20 * 1024 * 1024))  # 20MB
        
        config = load_config()
        
        assert config.max_file_size == 20 * 1024 * 1024
    
    def test_max_file_size_minimum_valid(self, monkeypatch):
        """Test that 1MB is accepted as minimum."""
        monkeypatch.setenv("HA_URL", "http://homeassistant.local:8123")
        monkeypatch.setenv("HA_TOKEN", "test_token")
        monkeypatch.setenv("MAX_FILE_SIZE", str(1 * 1024 * 1024))  # 1MB
        
        config = load_config()
        
        assert config.max_file_size == 1 * 1024 * 1024
    
    def test_max_file_size_maximum_valid(self, monkeypatch):
        """Test that 100MB is accepted as maximum."""
        monkeypatch.setenv("HA_URL", "http://homeassistant.local:8123")
        monkeypatch.setenv("HA_TOKEN", "test_token")
        monkeypatch.setenv("MAX_FILE_SIZE", str(100 * 1024 * 1024))  # 100MB
        
        config = load_config()
        
        assert config.max_file_size == 100 * 1024 * 1024
    
    def test_max_file_size_below_minimum(self, monkeypatch):
        """Test that values below 1MB are rejected."""
        monkeypatch.setenv("HA_URL", "http://homeassistant.local:8123")
        monkeypatch.setenv("HA_TOKEN", "test_token")
        monkeypatch.setenv("MAX_FILE_SIZE", str(512 * 1024))  # 512KB
        
        with pytest.raises(ConfigError) as exc_info:
            load_config()
        
        assert "MAX_FILE_SIZE must be at least" in str(exc_info.value)
        assert "1MB" in str(exc_info.value)
    
    def test_max_file_size_above_maximum(self, monkeypatch):
        """Test that values above 100MB are rejected."""
        monkeypatch.setenv("HA_URL", "http://homeassistant.local:8123")
        monkeypatch.setenv("HA_TOKEN", "test_token")
        monkeypatch.setenv("MAX_FILE_SIZE", str(150 * 1024 * 1024))  # 150MB
        
        with pytest.raises(ConfigError) as exc_info:
            load_config()
        
        assert "MAX_FILE_SIZE must not exceed" in str(exc_info.value)
        assert "100MB" in str(exc_info.value)
    
    def test_max_file_size_invalid_format(self, monkeypatch):
        """Test that non-integer values are rejected."""
        monkeypatch.setenv("HA_URL", "http://homeassistant.local:8123")
        monkeypatch.setenv("HA_TOKEN", "test_token")
        monkeypatch.setenv("MAX_FILE_SIZE", "not_a_number")
        
        with pytest.raises(ConfigError) as exc_info:
            load_config()
        
        assert "MAX_FILE_SIZE must be a valid integer" in str(exc_info.value)
    
    def test_max_file_size_zero(self, monkeypatch):
        """Test that zero is rejected."""
        monkeypatch.setenv("HA_URL", "http://homeassistant.local:8123")
        monkeypatch.setenv("HA_TOKEN", "test_token")
        monkeypatch.setenv("MAX_FILE_SIZE", "0")
        
        with pytest.raises(ConfigError) as exc_info:
            load_config()
        
        assert "MAX_FILE_SIZE must be at least" in str(exc_info.value)
    
    def test_max_file_size_negative(self, monkeypatch):
        """Test that negative values are rejected."""
        monkeypatch.setenv("HA_URL", "http://homeassistant.local:8123")
        monkeypatch.setenv("HA_TOKEN", "test_token")
        monkeypatch.setenv("MAX_FILE_SIZE", "-1048576")
        
        with pytest.raises(ConfigError) as exc_info:
            load_config()
        
        assert "MAX_FILE_SIZE must be at least" in str(exc_info.value)
