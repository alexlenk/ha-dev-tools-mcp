"""Tests for HAConfigurationManager cleanup functionality."""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from ha_config_manager.manager import HAConfigurationManager
from ha_config_manager.types import HAInstance, ConnectionType, ConnectionConfig


class TestManagerCleanup:
    """Test HAConfigurationManager cleanup functionality."""
    
    @pytest.mark.asyncio
    async def test_close_method_disconnects_all_connections(self):
        """Test that close() method disconnects all active connections."""
        manager = HAConfigurationManager()
        
        # Create mock connections
        mock_connection1 = Mock()
        mock_connection1.disconnect = AsyncMock()
        mock_connection2 = Mock()
        mock_connection2.disconnect = AsyncMock()
        
        # Add connections to manager
        manager._connections = {
            "instance1": mock_connection1,
            "instance2": mock_connection2
        }
        
        # Close manager
        await manager.close()
        
        # Verify all connections were disconnected
        mock_connection1.disconnect.assert_called_once()
        mock_connection2.disconnect.assert_called_once()
        
        # Verify internal state was cleared
        assert len(manager._connections) == 0
        assert len(manager._instances) == 0
        assert manager._current_instance_id is None
    
    @pytest.mark.asyncio
    async def test_close_method_handles_close_method(self):
        """Test that close() handles connections with close() instead of disconnect()."""
        manager = HAConfigurationManager()
        
        # Create mock connection with close() method
        mock_connection = Mock()
        mock_connection.close = AsyncMock()
        # No disconnect method
        mock_connection.disconnect = None
        
        manager._connections = {"instance1": mock_connection}
        
        # Close manager
        await manager.close()
        
        # Verify close was called
        mock_connection.close.assert_called_once()
        assert len(manager._connections) == 0
    
    @pytest.mark.asyncio
    async def test_close_method_handles_connection_errors(self):
        """Test that close() continues even if a connection fails to close."""
        manager = HAConfigurationManager()
        
        # Create mock connections, one that raises an error
        mock_connection1 = Mock()
        mock_connection1.disconnect = AsyncMock(side_effect=Exception("Connection error"))
        mock_connection2 = Mock()
        mock_connection2.disconnect = AsyncMock()
        
        manager._connections = {
            "instance1": mock_connection1,
            "instance2": mock_connection2
        }
        
        # Close should not raise an error
        await manager.close()
        
        # Both connections should have been attempted
        mock_connection1.disconnect.assert_called_once()
        mock_connection2.disconnect.assert_called_once()
        
        # State should still be cleared
        assert len(manager._connections) == 0
    
    @pytest.mark.asyncio
    async def test_close_method_handles_empty_manager(self):
        """Test that close() handles manager with no connections."""
        manager = HAConfigurationManager()
        
        # Manager has no connections
        assert len(manager._connections) == 0
        
        # Close should not raise an error
        await manager.close()
        
        # State should be cleared
        assert len(manager._connections) == 0
        assert len(manager._instances) == 0
        assert manager._current_instance_id is None
    
    @pytest.mark.asyncio
    async def test_close_clears_instances(self):
        """Test that close() clears all instance data."""
        manager = HAConfigurationManager()
        
        # Add some instance data
        manager._instances = {
            "instance1": Mock(),
            "instance2": Mock()
        }
        manager._current_instance_id = "instance1"
        
        # Close manager
        await manager.close()
        
        # Verify instances were cleared
        assert len(manager._instances) == 0
        assert manager._current_instance_id is None
