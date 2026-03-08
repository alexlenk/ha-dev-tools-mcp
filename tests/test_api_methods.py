"""Tests for HAAPIClient file and log access methods."""

import pytest
from aioresponses import aioresponses
from ha_dev_tools.connection.api import HAAPIClient, HAAPIError


class TestListFilesMethod:
    """Test list_files method."""
    
    @pytest.mark.asyncio
    async def test_list_files_without_directory(self):
        """Test listing files without directory filter."""
        client = HAAPIClient("http://ha.local:8123", "token")
        
        with aioresponses() as m:
            m.get(
                "http://ha.local:8123/api/management/files",
                payload={
                    'files': [
                        {'path': 'configuration.yaml', 'type': 'configuration'},
                        {'path': 'automations.yaml', 'type': 'automation'}
                    ]
                }
            )
            
            files = await client.list_files()
            
            # Verify files were returned
            assert len(files) == 2
            assert files[0]['path'] == 'configuration.yaml'
            assert files[1]['path'] == 'automations.yaml'
        
        await client.close()
    
    @pytest.mark.asyncio
    async def test_list_files_with_directory(self):
        """Test listing files with directory filter."""
        client = HAAPIClient("http://ha.local:8123", "token")
        
        with aioresponses() as m:
            m.get(
                "http://ha.local:8123/api/management/files?directory=packages",
                payload={
                    'files': [
                        {'path': 'packages/lights.yaml', 'type': 'package'}
                    ]
                }
            )
            
            files = await client.list_files(directory='packages')
            
            assert len(files) == 1
            assert 'packages' in files[0]['path']
        
        await client.close()


class TestReadFileMethod:
    """Test read_file method."""
    
    @pytest.mark.asyncio
    async def test_read_file_success(self):
        """Test reading file content successfully."""
        client = HAAPIClient("http://ha.local:8123", "token")
        
        file_content = """homeassistant:
  name: Home
  latitude: 37.7749
  longitude: -122.4194"""
        
        with aioresponses() as m:
            m.get(
                "http://ha.local:8123/api/management/files/configuration.yaml",
                body=file_content
            )
            
            result = await client.read_file('configuration.yaml')
            
            # Verify result structure
            assert isinstance(result, dict), "Result should be a dictionary"
            assert 'content' in result, "Result should have 'content' key"
            assert 'metadata' in result, "Result should have 'metadata' key"
            
            # Verify content was returned
            assert result['content'] == file_content
            assert 'homeassistant:' in result['content']
        
        await client.close()
    
    @pytest.mark.asyncio
    async def test_read_file_not_found(self):
        """Test reading non-existent file raises error."""
        client = HAAPIClient("http://ha.local:8123", "token")
        
        with aioresponses() as m:
            m.get(
                "http://ha.local:8123/api/management/files/nonexistent.yaml",
                status=404,
                body='{"message": "File not found"}'
            )
            
            with pytest.raises(HAAPIError) as exc_info:
                await client.read_file('nonexistent.yaml')
            
            assert exc_info.value.status_code == 404
            assert exc_info.value.error_code == "FILE_NOT_FOUND"
            assert 'nonexistent.yaml' in exc_info.value.message
        
        await client.close()


class TestGetLogsMethod:
    """Test get_logs method."""
    
    @pytest.mark.asyncio
    async def test_get_logs_basic(self):
        """Test getting logs with basic parameters."""
        client = HAAPIClient("http://ha.local:8123", "token")
        
        with aioresponses() as m:
            m.get(
                "http://ha.local:8123/api/management/logs/core?lines=100&offset=0&limit=100",
                payload={
                    'logs': [
                        {
                            'timestamp': '2024-01-15T10:30:00',
                            'level': 'INFO',
                            'message': 'Home Assistant started',
                            'logger': 'homeassistant.core'
                        }
                    ]
                }
            )
            
            logs = await client.get_logs('core')
            
            # Verify logs were returned
            assert len(logs) == 1
            assert logs[0]['level'] == 'INFO'
            assert logs[0]['message'] == 'Home Assistant started'
        
        await client.close()
    
    @pytest.mark.asyncio
    async def test_get_logs_with_filters(self):
        """Test getting logs with level and search filters."""
        client = HAAPIClient("http://ha.local:8123", "token")
        
        with aioresponses() as m:
            m.get(
                "http://ha.local:8123/api/management/logs/core?lines=50&offset=0&limit=25&level=ERROR&search=connection",
                payload={'logs': []}
            )
            
            logs = await client.get_logs(
                'core',
                level='ERROR',
                search='connection',
                lines=50,
                limit=25
            )
            
            # Verify empty logs were returned
            assert len(logs) == 0
        
        await client.close()
