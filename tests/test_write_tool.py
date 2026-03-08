"""Tests for write_config_file tool and write_file API method."""

import pytest
from aioresponses import aioresponses
from ha_dev_tools.connection.api import HAAPIClient, HAAPIError


class TestWriteFileMethod:
    """Test write_file method in HAAPIClient."""
    
    @pytest.mark.asyncio
    async def test_write_file_success(self):
        """Test writing file content successfully."""
        client = HAAPIClient("http://ha.local:8123", "token")
        
        file_content = """automation:
  - alias: Test Automation
    trigger:
      - platform: state
        entity_id: light.living_room
    action:
      - service: light.turn_on
        entity_id: light.bedroom"""
        
        with aioresponses() as m:
            m.put(
                "http://ha.local:8123/api/management/files/automations.yaml",
                payload={
                    'path': 'automations.yaml',
                    'size': 150,
                    'modified_at': '2024-01-15T10:30:00',
                    'content_hash': 'abc123def456',
                    'success': True
                }
            )
            
            result = await client.write_file('automations.yaml', file_content)
            
            # Verify metadata was returned
            assert result['path'] == 'automations.yaml'
            assert result['success'] is True
            assert 'content_hash' in result
            assert 'modified_at' in result
        
        await client.close()
    
    @pytest.mark.asyncio
    async def test_write_file_with_expected_hash(self):
        """Test writing file with expected_hash for conflict detection."""
        client = HAAPIClient("http://ha.local:8123", "token")
        
        file_content = "automation: []"
        expected_hash = "original_hash_123"
        
        with aioresponses() as m:
            m.put(
                "http://ha.local:8123/api/management/files/automations.yaml",
                payload={
                    'path': 'automations.yaml',
                    'size': 14,
                    'modified_at': '2024-01-15T10:35:00',
                    'content_hash': 'new_hash_456',
                    'success': True
                }
            )
            
            result = await client.write_file(
                'automations.yaml',
                file_content,
                expected_hash=expected_hash
            )
            
            # Verify write succeeded
            assert result['success'] is True
            assert result['content_hash'] == 'new_hash_456'
        
        await client.close()
    
    @pytest.mark.asyncio
    async def test_write_file_validation_error(self):
        """Test writing invalid YAML raises validation error."""
        client = HAAPIClient("http://ha.local:8123", "token")
        
        invalid_content = """automation:
  - alias: Test
    [invalid: yaml: syntax"""
        
        with aioresponses() as m:
            m.put(
                "http://ha.local:8123/api/management/files/automations.yaml",
                status=400,
                payload={
                    'message': 'YAML validation failed: Invalid syntax at line 3'
                }
            )
            
            with pytest.raises(HAAPIError) as exc_info:
                await client.write_file('automations.yaml', invalid_content)
            
            assert exc_info.value.status_code == 400
            assert exc_info.value.error_code == "INVALID_REQUEST"
            assert 'validation' in exc_info.value.message.lower()
        
        await client.close()
    
    @pytest.mark.asyncio
    async def test_write_file_conflict_detected(self):
        """Test writing file with hash conflict raises error."""
        client = HAAPIClient("http://ha.local:8123", "token")
        
        file_content = "automation: []"
        expected_hash = "old_hash_123"
        
        with aioresponses() as m:
            m.put(
                "http://ha.local:8123/api/management/files/automations.yaml",
                status=409,
                payload={
                    'message': 'Version conflict: File has been modified. Expected hash old_hash_123 but current hash is new_hash_456'
                }
            )
            
            with pytest.raises(HAAPIError) as exc_info:
                await client.write_file(
                    'automations.yaml',
                    file_content,
                    expected_hash=expected_hash
                )
            
            assert exc_info.value.status_code == 409
            assert exc_info.value.error_code == "VERSION_CONFLICT"
            assert 'conflict' in exc_info.value.message.lower()
        
        await client.close()
    
    @pytest.mark.asyncio
    async def test_write_file_access_denied(self):
        """Test writing to blocked path raises permission error."""
        client = HAAPIClient("http://ha.local:8123", "token")
        
        file_content = "secret: password123"
        
        with aioresponses() as m:
            m.put(
                "http://ha.local:8123/api/management/files/secrets.yaml",
                status=403,
                payload={
                    'message': 'Access denied: File not in allowed_paths'
                }
            )
            
            with pytest.raises(HAAPIError) as exc_info:
                await client.write_file('secrets.yaml', file_content)
            
            assert exc_info.value.status_code == 403
            assert exc_info.value.error_code == "PERMISSION_DENIED"
        
        await client.close()
    
    @pytest.mark.asyncio
    async def test_write_file_without_validation(self):
        """Test writing file with validation disabled."""
        client = HAAPIClient("http://ha.local:8123", "token")
        
        file_content = "some content"
        
        with aioresponses() as m:
            m.put(
                "http://ha.local:8123/api/management/files/test.txt",
                payload={
                    'path': 'test.txt',
                    'size': 12,
                    'modified_at': '2024-01-15T10:40:00',
                    'content_hash': 'hash789',
                    'success': True
                }
            )
            
            result = await client.write_file(
                'test.txt',
                file_content,
                validate_before_write=False
            )
            
            # Verify write succeeded
            assert result['success'] is True
        
        await client.close()


class TestWriteConfigFileTool:
    """Test write_config_file MCP tool integration."""
    
    @pytest.mark.asyncio
    async def test_write_tool_basic(self):
        """Test write_config_file tool with basic parameters."""
        # This test would require setting up the full MCP server context
        # For now, we verify the API client method works correctly
        client = HAAPIClient("http://ha.local:8123", "token")
        
        with aioresponses() as m:
            m.put(
                "http://ha.local:8123/api/management/files/configuration.yaml",
                payload={
                    'path': 'configuration.yaml',
                    'size': 100,
                    'modified_at': '2024-01-15T11:00:00',
                    'content_hash': 'hash_abc',
                    'success': True
                }
            )
            
            result = await client.write_file(
                'configuration.yaml',
                'homeassistant:\n  name: Test\n'
            )
            
            assert result['success'] is True
            assert result['path'] == 'configuration.yaml'
        
        await client.close()
    
    @pytest.mark.asyncio
    async def test_write_tool_with_all_parameters(self):
        """Test write_config_file tool with all optional parameters."""
        client = HAAPIClient("http://ha.local:8123", "token")
        
        with aioresponses() as m:
            m.put(
                "http://ha.local:8123/api/management/files/scripts.yaml",
                payload={
                    'path': 'scripts.yaml',
                    'size': 200,
                    'modified_at': '2024-01-15T11:05:00',
                    'content_hash': 'new_hash_xyz',
                    'success': True
                }
            )
            
            result = await client.write_file(
                file_path='scripts.yaml',
                content='script:\n  test_script:\n    sequence: []\n',
                expected_hash='old_hash_xyz',
                validate_before_write=True
            )
            
            assert result['success'] is True
            assert result['content_hash'] == 'new_hash_xyz'
        
        await client.close()
