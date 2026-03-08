"""Property-based tests for Configuration Manager.

These tests validate universal properties that should hold across all valid executions.
"""

import tempfile
from pathlib import Path
from typing import Any, Dict

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck

from ha_config_manager.manager import HAConfigurationManager
from ha_config_manager.types import (
    AuthConfig,
    AuthMethod,
    ConnectionConfig,
    ConnectionType,
    EncryptedCredentials,
    HAInstance,
    InstanceCapabilities,
)


# Hypothesis strategies for generating test data
@st.composite
def yaml_content(draw):
    """Generate valid YAML content."""
    name = draw(st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Pc'))))
    latitude = draw(st.floats(min_value=-90, max_value=90))
    longitude = draw(st.floats(min_value=-180, max_value=180))
    
    return f"""
homeassistant:
  name: {name}
  latitude: {latitude}
  longitude: {longitude}
"""


@st.composite
def invalid_yaml_content(draw):
    """Generate invalid YAML content."""
    # Common YAML syntax errors that are actually invalid
    error_types = [
        "unmatched_bracket",
        "unmatched_quote", 
        "invalid_tab_indentation",
        "invalid_character"
    ]
    
    error_type = draw(st.sampled_from(error_types))
    
    if error_type == "unmatched_bracket":
        return "homeassistant:\n  name: [invalid"
    elif error_type == "unmatched_quote":
        return "homeassistant:\n  name: \"unclosed quote"  # Unclosed quote
    elif error_type == "invalid_tab_indentation":
        return "homeassistant:\n\tname: test"  # Tab character (invalid in YAML)
    else:  # invalid_character
        return "homeassistant:\n  name: test\x00"  # Null character


@st.composite
def file_path(draw):
    """Generate valid file paths."""
    directories = [".", "packages", "automations", "scripts"]
    directory = draw(st.sampled_from(directories))
    filename = draw(st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'))))
    
    if directory == ".":
        return f"{filename}.yaml"
    else:
        return f"{directory}/{filename}.yaml"


async def create_test_manager():
    """Create a test manager instance."""
    temp_dir = tempfile.mkdtemp()
    ha_path = Path(temp_dir)
    
    # Create basic HA structure
    (ha_path / "configuration.yaml").write_text("""
homeassistant:
  name: Property Test
  latitude: 32.87336
  longitude: 117.22743
""")
    
    # Create directories
    for dir_name in ["packages", "automations", "scripts"]:
        (ha_path / dir_name).mkdir()
    
    # Create test instance
    instance = HAInstance(
        id="property_test",
        name="Property Test Instance",
        connection_type=ConnectionType.LOCAL,
        connection_config=ConnectionConfig(url=str(ha_path)),
        auth_config=AuthConfig(
            method=AuthMethod.TOKEN,
            credentials=EncryptedCredentials(
                encrypted_data="test_data",
                key_id="test_key",
                algorithm="AES256"
            )
        ),
        capabilities=InstanceCapabilities(
            has_file_access=True,
            has_addons=False,
            has_custom_components=False,
            supported_apis=["rest"]
        )
    )
    
    manager = HAConfigurationManager()
    await manager.add_instance(instance)
    await manager.switch_instance(instance.id)
    
    return manager, instance.id, ha_path


class TestConfigurationProperties:
    """Property-based tests for configuration management."""
    
    @given(yaml_content())
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_property_1_config_file_discovery_and_access(self, content: str):
        """
        **Feature: home-assistant-development, Property 1: Configuration File Discovery and Access**
        
        For any Home Assistant instance, discovering configuration files should return all packages, 
        automations, and scripts, and reading any discovered file should return complete YAML content 
        with proper formatting preserved.
        
        **Validates: Requirements 1.1, 1.2**
        """
        manager, instance_id, ha_path = await create_test_manager()
        
        # Write test file
        test_file = "test_property.yaml"
        await manager.write_config_file(instance_id, test_file, content)
        
        # Property: Discovery should find the file
        files = await manager.list_config_files(instance_id)
        file_paths = [f.path for f in files]
        assert test_file in file_paths, "Discovery should find all configuration files"
        
        # Property: Reading should return complete content with formatting preserved
        read_content = await manager.read_config_file(instance_id, test_file)
        assert read_content.strip() == content.strip(), "Content should be preserved exactly"
    
    @given(st.text(min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'Pc'))))
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_property_2_backup_creation(self, file_content: str):
        """
        **Feature: home-assistant-development, Property 2: Configuration Backup Creation**
        
        For any configuration file modification operation, a backup should be created before 
        the change is applied, and the backup should contain the exact original content.
        
        **Validates: Requirements 1.4**
        """
        manager, instance_id, ha_path = await create_test_manager()
        
        # Create original file with valid YAML (sanitize content for YAML safety)
        safe_content = file_content.replace(':', '_').replace('\n', ' ').replace('\r', ' ').replace('=', '_')
        original_content = f"""homeassistant:
  name: {safe_content}
  latitude: 32.87336
  longitude: 117.22743"""
        
        test_file = "backup_test.yaml"
        await manager.write_config_file(instance_id, test_file, original_content)
        
        # Property: Backup creation should preserve exact original content
        backup_path = await manager.create_backup(instance_id, test_file)
        backup_content = await manager.read_config_file(instance_id, backup_path)
        
        assert backup_content == original_content, "Backup should contain exact original content"
        assert backup_path != test_file, "Backup should have different path than original"
        assert test_file in backup_path, "Backup path should reference original file"
    
    @given(yaml_content())
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_property_3_yaml_validation_consistency_valid(self, content: str):
        """
        **Feature: home-assistant-development, Property 3: YAML Validation Consistency (Valid)**
        
        For any valid YAML content, validation should accept it consistently and check 
        syntax, structure, and HA-specific schema compliance.
        
        **Validates: Requirements 1.3, 6.1, 6.2**
        """
        manager, instance_id, ha_path = await create_test_manager()
        
        # Property: Valid YAML should always be accepted
        result = await manager.validate_yaml(content)
        assert result.valid is True, "Valid YAML should always pass validation"
        assert len(result.errors) == 0, "Valid YAML should have no errors"
    
    @given(invalid_yaml_content())
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_property_3_yaml_validation_consistency_invalid(self, content: str):
        """
        **Feature: home-assistant-development, Property 3: YAML Validation Consistency (Invalid)**
        
        For any invalid YAML content, validation should reject it consistently and provide 
        appropriate error information.
        
        **Validates: Requirements 1.3, 6.1, 6.2**
        """
        manager, instance_id, ha_path = await create_test_manager()
        
        # Property: Invalid YAML should always be rejected
        result = await manager.validate_yaml(content)
        assert result.valid is False, "Invalid YAML should always fail validation"
        assert len(result.errors) > 0, "Invalid YAML should have error messages"
        assert all(error.code for error in result.errors), "All errors should have error codes"