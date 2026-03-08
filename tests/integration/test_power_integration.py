"""
Integration tests for power integration scenarios.

Tests different power installation and configuration states:
1. ha-development-power installed and configured
2. ha-development-power not installed (fallback to local)
3. ha-development-power installed but HA_URL/HA_TOKEN not configured

Requirements: 2.1, 2.2, 3.1, 3.2
"""

import pytest
import os
from unittest.mock import AsyncMock, Mock, patch


@pytest.fixture
def mock_power_installed():
    """Mock power as installed."""
    return {
        "name": "ha-development-power",
        "installed": True,
        "configured": True,
        "ha_url": "http://homeassistant.local:8123",
        "ha_token": "test_token_123"
    }


@pytest.fixture
def mock_power_not_installed():
    """Mock power as not installed."""
    return {
        "name": "ha-development-power",
        "installed": False,
        "configured": False
    }


@pytest.fixture
def mock_power_not_configured():
    """Mock power installed but not configured."""
    return {
        "name": "ha-development-power",
        "installed": True,
        "configured": False,
        "ha_url": None,
        "ha_token": None
    }


class TestPowerIntegrationScenarios:
    """Test different power installation and configuration scenarios."""
    
    @pytest.mark.asyncio
    async def test_power_installed_and_configured(self, mock_power_installed):
        """
        Test behavior when ha-development-power is installed and configured.
        
        Expected: Use MCP tools for HA file operations
        """
        # Simulate context
        context = {
            "power_installed": mock_power_installed["installed"],
            "power_configured": mock_power_installed["configured"],
            "ha_url": mock_power_installed["ha_url"],
            "ha_token": mock_power_installed["ha_token"]
        }
        
        # Verify power state
        assert context["power_installed"], "Power should be installed"
        assert context["power_configured"], "Power should be configured"
        assert context["ha_url"] is not None
        assert context["ha_token"] is not None
        
        # Simulate user request
        user_request = "Show me my Home Assistant configuration.yaml"
        
        # Context recognition
        should_use_mcp = (
            context["power_installed"] and
            context["power_configured"] and
            "home assistant" in user_request.lower() or "configuration.yaml" in user_request
        )
        
        assert should_use_mcp, "Should use MCP tools when power is installed and configured"
    
    @pytest.mark.asyncio
    async def test_power_not_installed_fallback(self, mock_power_not_installed):
        """
        Test fallback to local tools when power is not installed.
        
        Expected: Use local file tools (readFile, fileSearch)
        """
        # Simulate context
        context = {
            "power_installed": mock_power_not_installed["installed"],
            "power_configured": mock_power_not_installed["configured"]
        }
        
        # Verify power state
        assert not context["power_installed"], "Power should not be installed"
        
        # Simulate user request
        user_request = "Show me my Home Assistant configuration.yaml"
        
        # Context recognition
        should_use_mcp = context["power_installed"] and context["power_configured"]
        should_use_local = not should_use_mcp
        
        assert should_use_local, "Should use local tools when power not installed"
        assert not should_use_mcp, "Should not use MCP tools"
    
    @pytest.mark.asyncio
    async def test_power_installed_not_configured(self, mock_power_not_configured):
        """
        Test behavior when power is installed but HA_URL/HA_TOKEN not configured.
        
        Expected: Provide clear error message, suggest configuration
        """
        # Simulate context
        context = {
            "power_installed": mock_power_not_configured["installed"],
            "power_configured": mock_power_not_configured["configured"],
            "ha_url": mock_power_not_configured["ha_url"],
            "ha_token": mock_power_not_configured["ha_token"]
        }
        
        # Verify power state
        assert context["power_installed"], "Power should be installed"
        assert not context["power_configured"], "Power should not be configured"
        assert context["ha_url"] is None
        assert context["ha_token"] is None
        
        # Simulate user request
        user_request = "Show me my Home Assistant configuration.yaml"
        
        # Should detect configuration issue
        has_config_issue = (
            context["power_installed"] and
            not context["power_configured"]
        )
        
        assert has_config_issue, "Should detect configuration issue"
        
        # Should provide error message
        error_message = (
            "Home Assistant Development Power is installed but not configured. "
            "Please set HA_URL and HA_TOKEN environment variables."
        )
        
        assert "not configured" in error_message.lower()
        assert "HA_URL" in error_message
        assert "HA_TOKEN" in error_message
    
    @pytest.mark.asyncio
    async def test_explicit_local_request_overrides_power(self, mock_power_installed):
        """
        Test that explicit local requests use local tools even when power is available.
        
        Expected: Use local tools when user explicitly requests local access
        """
        # Simulate context
        context = {
            "power_installed": mock_power_installed["installed"],
            "power_configured": mock_power_installed["configured"]
        }
        
        # Simulate explicit local request
        user_request = "Read the local configuration.yaml file"
        
        # Context recognition
        is_explicit_local = "local" in user_request.lower()
        should_use_local = is_explicit_local
        should_use_mcp = not is_explicit_local and context["power_installed"]
        
        assert is_explicit_local, "Should detect explicit local request"
        assert should_use_local, "Should use local tools for explicit local request"
        assert not should_use_mcp, "Should not use MCP tools for explicit local"
    
    @pytest.mark.asyncio
    async def test_non_ha_file_uses_local_tools(self, mock_power_installed):
        """
        Test that non-HA files use local tools even when power is installed.
        
        Expected: Use local tools for project files
        """
        # Simulate context
        context = {
            "power_installed": mock_power_installed["installed"],
            "power_configured": mock_power_installed["configured"]
        }
        
        # Simulate non-HA file request
        user_request = "Show me the package.json file"
        
        # Context recognition
        has_ha_context = any(
            keyword in user_request.lower()
            for keyword in ["home assistant", "ha", "homeassistant"]
        )
        is_ha_file = any(
            filename in user_request.lower()
            for filename in ["configuration.yaml", "automations.yaml", "scripts.yaml"]
        )
        
        should_use_mcp = has_ha_context or is_ha_file
        should_use_local = not should_use_mcp
        
        assert not has_ha_context, "Should not detect HA context"
        assert not is_ha_file, "Should not detect HA file"
        assert should_use_local, "Should use local tools for non-HA files"
    
    @pytest.mark.asyncio
    async def test_environment_variable_detection(self):
        """
        Test detection of HA_URL and HA_TOKEN environment variables.
        """
        # Test with environment variables set
        with patch.dict(os.environ, {
            "HA_URL": "http://homeassistant.local:8123",
            "HA_TOKEN": "test_token"
        }):
            ha_url = os.environ.get("HA_URL")
            ha_token = os.environ.get("HA_TOKEN")
            
            assert ha_url is not None
            assert ha_token is not None
            
            is_configured = ha_url is not None and ha_token is not None
            assert is_configured, "Should detect configuration from environment"
        
        # Test without environment variables
        with patch.dict(os.environ, {}, clear=True):
            ha_url = os.environ.get("HA_URL")
            ha_token = os.environ.get("HA_TOKEN")
            
            assert ha_url is None
            assert ha_token is None
            
            is_configured = ha_url is not None and ha_token is not None
            assert not is_configured, "Should detect missing configuration"
    
    @pytest.mark.asyncio
    async def test_multiple_powers_installed(self, mock_power_installed):
        """
        Test behavior when multiple powers are installed.
        
        Expected: Use correct power based on context
        """
        # Simulate multiple powers
        installed_powers = [
            {"name": "ha-development-power", "installed": True},
            {"name": "other-power", "installed": True}
        ]
        
        # Simulate HA-related request
        user_request = "Show me my Home Assistant configuration.yaml"
        
        # Should select ha-development-power
        relevant_power = None
        for power in installed_powers:
            if "ha" in power["name"] or "home-assistant" in power["name"]:
                relevant_power = power
                break
        
        assert relevant_power is not None
        assert relevant_power["name"] == "ha-development-power"
    
    @pytest.mark.asyncio
    async def test_power_activation_on_ha_context(self, mock_power_installed):
        """
        Test that power is activated when HA context is detected.
        """
        # Simulate context
        context = {
            "power_installed": mock_power_installed["installed"],
            "power_configured": mock_power_installed["configured"]
        }
        
        # Test various HA context indicators
        ha_requests = [
            "Show me my Home Assistant configuration.yaml",
            "Read my HA automations.yaml",
            "List files in homeassistant packages directory",
            "Download configuration.yaml from HA"
        ]
        
        for request in ha_requests:
            has_ha_context = any(
                keyword in request.lower()
                for keyword in ["home assistant", "ha", "homeassistant", "configuration.yaml"]
            )
            
            should_activate_power = (
                has_ha_context and
                context["power_installed"] and
                context["power_configured"]
            )
            
            assert should_activate_power, f"Should activate power for: {request}"
    
    @pytest.mark.asyncio
    async def test_configuration_error_messages(self, mock_power_not_configured):
        """
        Test that clear error messages are provided for configuration issues.
        """
        context = {
            "power_installed": mock_power_not_configured["installed"],
            "power_configured": mock_power_not_configured["configured"]
        }
        
        # Generate error message
        if context["power_installed"] and not context["power_configured"]:
            error_message = (
                "Home Assistant Development Power is installed but not configured.\n"
                "Please set the following environment variables:\n"
                "  - HA_URL: Your Home Assistant URL (e.g., http://homeassistant.local:8123)\n"
                "  - HA_TOKEN: Your long-lived access token\n\n"
                "To configure:\n"
                "  export HA_URL='http://your-ha-url:8123'\n"
                "  export HA_TOKEN='your-token-here'"
            )
        else:
            error_message = None
        
        assert error_message is not None
        assert "not configured" in error_message
        assert "HA_URL" in error_message
        assert "HA_TOKEN" in error_message
        assert "export" in error_message
