"""Integration tests for server startup and initialization.

Tests verify:
- Server can be imported and initialized
- Server fails with missing configuration
- Entry point module works correctly
"""

import pytest
import os
from unittest.mock import patch
from ha_dev_tools.config import ConfigError


class TestServerStartup:
    """Integration tests for server startup."""
    
    def test_server_module_can_be_imported(self):
        """Test that the server module can be imported successfully."""
        # This test verifies the module structure is correct
        from ha_dev_tools import server
        assert hasattr(server, 'main')
        assert callable(server.main)
    
    def test_main_module_can_be_imported(self):
        """Test that the __main__ module can be imported successfully."""
        from ha_dev_tools import __main__
        assert hasattr(__main__, 'run')
        assert callable(__main__.run)
    
    @pytest.mark.asyncio
    async def test_server_fails_with_missing_ha_url(self):
        """Test that server fails to start when HA_URL is missing."""
        from ha_dev_tools.server import main
        
        # Clear environment variables
        env = os.environ.copy()
        if 'HA_URL' in env:
            del env['HA_URL']
        if 'HA_TOKEN' in env:
            del env['HA_TOKEN']
        
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ConfigError) as exc_info:
                await main()
            
            assert "HA_URL" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_server_fails_with_missing_ha_token(self):
        """Test that server fails to start when HA_TOKEN is missing."""
        from ha_dev_tools.server import main
        
        # Set only HA_URL, not HA_TOKEN
        env = {'HA_URL': 'http://localhost:8123'}
        
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ConfigError) as exc_info:
                await main()
            
            assert "HA_TOKEN" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_server_fails_with_invalid_url_format(self):
        """Test that server fails to start when HA_URL has invalid format."""
        from ha_dev_tools.server import main
        
        # Set invalid URL format
        env = {
            'HA_URL': 'not-a-valid-url',
            'HA_TOKEN': 'test-token'
        }
        
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(ConfigError) as exc_info:
                await main()
            
            assert "http://" in str(exc_info.value) or "https://" in str(exc_info.value)
    
    def test_main_module_entry_point_handles_keyboard_interrupt(self):
        """Test that the entry point handles KeyboardInterrupt gracefully."""
        from ha_dev_tools.__main__ import run
        
        # Mock asyncio.run to raise KeyboardInterrupt
        with patch('ha_dev_tools.__main__.asyncio.run', side_effect=KeyboardInterrupt):
            with pytest.raises(SystemExit) as exc_info:
                run()
            
            # Should exit with code 0 (graceful shutdown)
            assert exc_info.value.code == 0
    
    def test_main_module_entry_point_handles_exceptions(self):
        """Test that the entry point handles exceptions and exits with error code."""
        from ha_dev_tools.__main__ import run
        
        # Mock asyncio.run to raise a generic exception
        with patch('ha_dev_tools.__main__.asyncio.run', side_effect=RuntimeError("Test error")):
            with pytest.raises(SystemExit) as exc_info:
                run()
            
            # Should exit with code 1 (error)
            assert exc_info.value.code == 1
    
    def test_main_module_can_be_run_as_module(self):
        """Test that the package can be run as a module (python -m ha_dev_tools)."""
        # This test verifies the __main__.py structure is correct
        import importlib.util
        
        # Find the __main__.py module
        spec = importlib.util.find_spec('ha_dev_tools.__main__')
        assert spec is not None
        assert spec.origin.endswith('__main__.py')
        
        # Verify it has the required entry point
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        assert hasattr(module, 'run')
        assert callable(module.run)
        assert hasattr(module, '__name__')
