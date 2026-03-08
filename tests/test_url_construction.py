"""Unit tests for URL construction and encoding."""

import pytest
from aioresponses import aioresponses
from ha_dev_tools.connection.api import HAAPIClient


class TestURLConstruction:
    """Tests for URL construction and parameter encoding."""
    
    @pytest.mark.asyncio
    async def test_file_path_properly_encoded_in_url(self):
        """Test that file_path with special characters is properly encoded in URL."""
        client = HAAPIClient("http://ha.local:8123", "test_token")
        
        with aioresponses() as m:
            # File path with spaces should be URL encoded
            m.get(
                "http://ha.local:8123/api/ha_dev_tools/files/my%20config.yaml",
                status=200,
                body='homeassistant:\n  name: Home'
            )
            
            result = await client.read_file("my config.yaml")
            
            assert result is not None
        
        await client.close()
    
    @pytest.mark.asyncio
    async def test_file_path_with_subdirectory_encoded(self):
        """Test that file_path with subdirectory is properly encoded."""
        client = HAAPIClient("http://ha.local:8123", "test_token")
        
        with aioresponses() as m:
            # Subdirectory path should be properly encoded
            m.get(
                "http://ha.local:8123/api/ha_dev_tools/files/packages/lights.yaml",
                status=200,
                body='light:\n  - platform: hue'
            )
            
            result = await client.read_file("packages/lights.yaml")
            
            assert result is not None
        
        await client.close()
    
    @pytest.mark.asyncio
    async def test_file_path_with_special_characters_encoded(self):
        """Test that file_path with special characters is properly URL encoded."""
        client = HAAPIClient("http://ha.local:8123", "test_token")
        
        with aioresponses() as m:
            # Special characters like & and = should be encoded
            m.get(
                "http://ha.local:8123/api/ha_dev_tools/files/test%26file%3Dconfig.yaml",
                status=200,
                body='test: data'
            )
            
            result = await client.read_file("test&file=config.yaml")
            
            assert result is not None
        
        await client.close()
    
    @pytest.mark.asyncio
    async def test_log_source_properly_included_in_url(self):
        """Test that log_source is properly included in URL path."""
        client = HAAPIClient("http://ha.local:8123", "test_token")
        
        with aioresponses() as m:
            # log_source should be part of the URL path
            m.get(
                "http://ha.local:8123/api/ha_dev_tools/logs/core?lines=100&offset=0&limit=100",
                status=200,
                body='{"logs": [], "total_count": 0, "source": "core"}'
            )
            
            result = await client.get_logs(log_source="core")
            
            assert result is not None
        
        await client.close()
    
    @pytest.mark.asyncio
    async def test_entity_id_properly_encoded_in_url(self):
        """Test that entity_id with special characters is properly encoded in URL."""
        client = HAAPIClient("http://ha.local:8123", "test_token")
        
        with aioresponses() as m:
            # Entity ID with dots should be properly encoded
            m.get(
                "http://ha.local:8123/api/states/sensor.living_room_temperature",
                status=200,
                body='{"entity_id": "sensor.living_room_temperature", "state": "22.5"}'
            )
            
            result = await client.get_states("sensor.living_room_temperature")
            
            assert result is not None
        
        await client.close()
    
    @pytest.mark.asyncio
    async def test_entity_id_with_special_characters_encoded(self):
        """Test that entity_id with unusual characters is properly encoded."""
        client = HAAPIClient("http://ha.local:8123", "test_token")
        
        with aioresponses() as m:
            # Entity ID with underscores and numbers
            m.get(
                "http://ha.local:8123/api/states/sensor.temp_sensor_1",
                status=200,
                body='{"entity_id": "sensor.temp_sensor_1", "state": "20.0"}'
            )
            
            result = await client.get_states("sensor.temp_sensor_1")
            
            assert result is not None
        
        await client.close()
    
    @pytest.mark.asyncio
    async def test_domain_service_properly_encoded_in_url(self):
        """Test that domain and service are properly encoded in URL."""
        client = HAAPIClient("http://ha.local:8123", "test_token")
        
        with aioresponses() as m:
            # Domain and service should be part of URL path
            m.post(
                "http://ha.local:8123/api/services/light/turn_on",
                status=200,
                body='[{"entity_id": "light.living_room", "state": "on"}]'
            )
            
            result = await client.call_service("light", "turn_on")
            
            assert result is not None
        
        await client.close()
    
    @pytest.mark.asyncio
    async def test_domain_service_with_underscores_encoded(self):
        """Test that domain and service with underscores are properly encoded."""
        client = HAAPIClient("http://ha.local:8123", "test_token")
        
        with aioresponses() as m:
            # Service names with underscores
            m.post(
                "http://ha.local:8123/api/services/homeassistant/reload_config_entry",
                status=200,
                body='[]'
            )
            
            result = await client.call_service("homeassistant", "reload_config_entry")
            
            assert result is not None
        
        await client.close()
    
    @pytest.mark.asyncio
    async def test_url_construction_with_base_url_trailing_slash(self):
        """Test that URL construction works correctly even if base_url has trailing slash."""
        # Create client with trailing slash in base_url
        client = HAAPIClient("http://ha.local:8123/", "test_token")
        
        with aioresponses() as m:
            # Should handle trailing slash correctly
            m.get(
                "http://ha.local:8123/api/ha_dev_tools/files",
                status=200,
                body='{"files": [], "directory": ""}'
            )
            
            result = await client.list_files()
            
            assert result is not None
        
        await client.close()
    
    @pytest.mark.asyncio
    async def test_url_construction_preserves_port(self):
        """Test that URL construction preserves custom port numbers."""
        client = HAAPIClient("http://ha.local:8123", "test_token")
        
        with aioresponses() as m:
            # Port should be preserved in URL
            m.get(
                "http://ha.local:8123/api/states",
                status=200,
                body='[]'
            )
            
            result = await client.get_states()
            
            assert result is not None
        
        await client.close()
    
    @pytest.mark.asyncio
    async def test_url_construction_with_https(self):
        """Test that URL construction works with HTTPS protocol."""
        client = HAAPIClient("https://ha.example.com", "test_token")
        
        with aioresponses() as m:
            # HTTPS should be preserved
            m.get(
                "https://ha.example.com/api/config",
                status=200,
                body='{"version": "2024.1.0"}'
            )
            
            result = await client.get_config()
            
            assert result is not None
        
        await client.close()
    
    @pytest.mark.asyncio
    async def test_url_construction_with_ip_address(self):
        """Test that URL construction works with IP address."""
        client = HAAPIClient("http://192.168.1.100:8123", "test_token")
        
        with aioresponses() as m:
            # IP address should work correctly
            m.get(
                "http://192.168.1.100:8123/api/events",
                status=200,
                body='[]'
            )
            
            result = await client.list_events()
            
            assert result is not None
        
        await client.close()
