"""Unit tests for specific error scenarios."""

import pytest
import asyncio
from aiohttp import ClientError
from aioresponses import aioresponses
from ha_dev_tools.connection.api import HAAPIClient, HAAPIError


class TestSpecificErrorScenarios:
    """Tests for specific error scenarios as defined in requirements."""
    
    @pytest.mark.asyncio
    async def test_404_error_returns_file_not_found_message(self):
        """Test that 404 error returns 'File not found' message for files."""
        client = HAAPIClient("http://ha.local:8123", "test_token")
        
        with aioresponses() as m:
            m.get(
                "http://ha.local:8123/api/management/files/missing.yaml",
                status=404,
                body='{"message": "File not found"}'
            )
            
            with pytest.raises(HAAPIError) as exc_info:
                await client.read_file("missing.yaml")
            
            assert exc_info.value.status_code == 404
            assert "File not found" in exc_info.value.message
            assert "missing.yaml" in exc_info.value.message
        
        await client.close()
    
    @pytest.mark.asyncio
    async def test_404_error_returns_entity_not_found_message(self):
        """Test that 404 error returns 'Entity not found' or 'Resource not found' message for entities."""
        client = HAAPIClient("http://ha.local:8123", "test_token")
        
        with aioresponses() as m:
            m.get(
                "http://ha.local:8123/api/states/light.nonexistent",
                status=404,
                body='{"message": "Entity not found"}'
            )
            
            with pytest.raises(HAAPIError) as exc_info:
                await client.get_states("light.nonexistent")
            
            assert exc_info.value.status_code == 404
            # Should contain "not found" in the message
            assert "not found" in exc_info.value.message.lower()
        
        await client.close()
    
    @pytest.mark.asyncio
    async def test_401_error_returns_authentication_message(self):
        """Test that 401 error returns authentication message."""
        client = HAAPIClient("http://ha.local:8123", "invalid_token")
        
        with aioresponses() as m:
            m.get(
                "http://ha.local:8123/api/management/files",
                status=401,
                body='{"message": "Unauthorized"}'
            )
            
            with pytest.raises(HAAPIError) as exc_info:
                await client.list_files()
            
            assert exc_info.value.status_code == 401
            assert exc_info.value.error_code == "AUTHENTICATION_FAILED"
            assert "Authentication failed" in exc_info.value.message
            assert "HA_TOKEN" in exc_info.value.message
        
        await client.close()
    
    @pytest.mark.asyncio
    async def test_403_error_returns_permission_message(self):
        """Test that 403 error returns permission message."""
        client = HAAPIClient("http://ha.local:8123", "limited_token")
        
        with aioresponses() as m:
            m.get(
                "http://ha.local:8123/api/management/files/secrets.yaml",
                status=403,
                body='{"message": "Forbidden"}'
            )
            
            with pytest.raises(HAAPIError) as exc_info:
                await client.read_file("secrets.yaml")
            
            assert exc_info.value.status_code == 403
            assert exc_info.value.error_code == "PERMISSION_DENIED"
            assert "Permission denied" in exc_info.value.message
            assert "permissions" in exc_info.value.message
        
        await client.close()
    
    @pytest.mark.asyncio
    async def test_400_error_includes_api_validation_message(self):
        """Test that 400 error includes API validation message."""
        client = HAAPIClient("http://ha.local:8123", "test_token")
        
        with aioresponses() as m:
            # Use the correct URL format with query parameters
            m.get(
                "http://ha.local:8123/api/management/logs/invalid_source?lines=100&offset=0&limit=100",
                status=400,
                body='{"message": "Invalid log source. Supported: core"}'
            )
            
            with pytest.raises(HAAPIError) as exc_info:
                await client.get_logs("invalid_source")
            
            assert exc_info.value.status_code == 400
            assert exc_info.value.error_code == "INVALID_REQUEST"
            assert "Invalid log source" in exc_info.value.message
        
        await client.close()
    
    @pytest.mark.asyncio
    async def test_500_error_returns_server_error_message(self):
        """Test that 500 error returns server error message."""
        client = HAAPIClient("http://ha.local:8123", "test_token")
        
        with aioresponses() as m:
            m.get(
                "http://ha.local:8123/api/management/files",
                status=500,
                body='{"message": "Internal server error"}'
            )
            
            with pytest.raises(HAAPIError) as exc_info:
                await client.list_files()
            
            assert exc_info.value.status_code == 500
            assert exc_info.value.error_code == "SERVER_ERROR"
            assert "server error" in exc_info.value.message.lower()
        
        await client.close()
    
    @pytest.mark.asyncio
    async def test_network_timeout_returns_connectivity_message(self):
        """Test that network timeout returns connectivity message."""
        client = HAAPIClient("http://ha.local:8123", "test_token")
        
        with aioresponses() as m:
            # Simulate timeout by raising asyncio.TimeoutError
            m.get(
                "http://ha.local:8123/api/management/files",
                exception=asyncio.TimeoutError("Connection timeout")
            )
            
            with pytest.raises(HAAPIError) as exc_info:
                await client.list_files()
            
            # Should indicate connectivity issue - check for "timed out" or "timeout"
            message_lower = exc_info.value.message.lower()
            assert "timed out" in message_lower or "timeout" in message_lower or "unreachable" in message_lower
        
        await client.close()
    
    @pytest.mark.asyncio
    async def test_connection_error_returns_connectivity_message(self):
        """Test that connection error returns connectivity message."""
        client = HAAPIClient("http://ha.local:8123", "test_token")
        
        with aioresponses() as m:
            # Simulate connection error
            m.get(
                "http://ha.local:8123/api/management/files",
                exception=ClientError("Connection refused")
            )
            
            with pytest.raises(HAAPIError) as exc_info:
                await client.list_files()
            
            # Should indicate connectivity issue
            assert "unreachable" in exc_info.value.message.lower() or "connection" in exc_info.value.message.lower()
        
        await client.close()
    
    @pytest.mark.asyncio
    async def test_template_syntax_error_returns_error_message(self):
        """Test that template syntax error returns error message."""
        client = HAAPIClient("http://ha.local:8123", "test_token")
        
        with aioresponses() as m:
            # Template syntax errors typically return 400 with error details
            m.post(
                "http://ha.local:8123/api/template",
                status=400,
                body='{"message": "TemplateSyntaxError: unexpected end of template"}'
            )
            
            with pytest.raises(HAAPIError) as exc_info:
                await client.render_template("{{ invalid template")
            
            assert exc_info.value.status_code == 400
            assert "template" in exc_info.value.message.lower() or "syntax" in exc_info.value.message.lower()
        
        await client.close()
    
    @pytest.mark.asyncio
    async def test_service_not_found_returns_error_message(self):
        """Test that calling non-existent service returns error message."""
        client = HAAPIClient("http://ha.local:8123", "test_token")
        
        with aioresponses() as m:
            m.post(
                "http://ha.local:8123/api/services/light/nonexistent_service",
                status=404,
                body='{"message": "Service not found"}'
            )
            
            with pytest.raises(HAAPIError) as exc_info:
                await client.call_service("light", "nonexistent_service")
            
            assert exc_info.value.status_code == 404
            assert "not found" in exc_info.value.message.lower()
        
        await client.close()
    
    @pytest.mark.asyncio
    async def test_502_bad_gateway_returns_unavailable_message(self):
        """Test that 502 Bad Gateway returns service unavailable message."""
        client = HAAPIClient("http://ha.local:8123", "test_token")
        
        with aioresponses() as m:
            m.get(
                "http://ha.local:8123/api/states",
                status=502,
                body='Bad Gateway'
            )
            
            with pytest.raises(HAAPIError) as exc_info:
                await client.get_states()
            
            assert exc_info.value.status_code == 502
            assert exc_info.value.error_code == "SERVICE_UNAVAILABLE"
            assert "unavailable" in exc_info.value.message.lower()
        
        await client.close()
    
    @pytest.mark.asyncio
    async def test_503_service_unavailable_returns_unavailable_message(self):
        """Test that 503 Service Unavailable returns appropriate message."""
        client = HAAPIClient("http://ha.local:8123", "test_token")
        
        with aioresponses() as m:
            m.get(
                "http://ha.local:8123/api/config",
                status=503,
                body='Service Unavailable'
            )
            
            with pytest.raises(HAAPIError) as exc_info:
                await client.get_config()
            
            assert exc_info.value.status_code == 503
            assert exc_info.value.error_code == "SERVICE_UNAVAILABLE"
            assert "unavailable" in exc_info.value.message.lower()
        
        await client.close()
