"""Property-based tests for HAConfigurationManager integration with FileSaver."""

import asyncio
import pytest
from unittest.mock import AsyncMock, Mock, patch
from hypothesis import given, strategies as st, settings, HealthCheck

from ha_dev_tools.manager import HAConfigurationManager
from ha_dev_tools.types import SaveResult

# Strategy for generating valid file content
file_content_strategy = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",)),  # Exclude surrogates
    min_size=0,
    max_size=1000,
)

# Strategy for generating valid file paths
file_path_strategy = st.text(
    alphabet=st.characters(
        whitelist_categories=("L", "N"), min_codepoint=32, max_codepoint=126
    ),
    min_size=1,
    max_size=50,
).filter(lambda x: ".." not in x and not x.startswith("/") and not x.startswith("\\"))


@given(content=file_content_strategy)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_backward_compatibility_with_false(content):
    """Property 2: Backward Compatibility Preserved - save_local=False.

    For any file, when save_local=False, verify response contains content field
    and does NOT contain local_path field.
    """

    async def run_test():
        manager = HAConfigurationManager()

        # Setup mock connection
        mock_connection = Mock()
        mock_connection.read_file = AsyncMock(return_value=content)
        manager._connections["test_instance"] = mock_connection

        # Execute with save_local=False
        result = await manager.read_config_file(
            instance_id="test_instance", file_path="test.yaml", save_local=False
        )

        # Verify
        assert result["saved"] is False
        assert "content" in result
        assert result["content"] == content
        assert "local_path" not in result
        assert "file_path" in result
        assert "file_size" in result

    asyncio.run(run_test())


@given(content=file_content_strategy)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_backward_compatibility_without_param(content):
    """Property 2: Backward Compatibility Preserved - save_local omitted.

    For any file, when save_local is omitted, verify response contains content field
    and does NOT contain local_path field.
    """

    async def run_test():
        manager = HAConfigurationManager()

        # Setup mock connection
        mock_connection = Mock()
        mock_connection.read_file = AsyncMock(return_value=content)
        manager._connections["test_instance"] = mock_connection

        # Execute without save_local parameter
        result = await manager.read_config_file(
            instance_id="test_instance", file_path="test.yaml"
        )

        # Verify
        assert result["saved"] is False
        assert "content" in result
        assert result["content"] == content
        assert "local_path" not in result
        assert "file_path" in result
        assert "file_size" in result

    asyncio.run(run_test())


@given(content=file_content_strategy, file_path=file_path_strategy)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_save_response_completeness(content, file_path):
    """Property 3: Save Response Completeness.

    For any successful save, verify response has local_path, file_size, remote_path
    and all fields have non-empty values.
    """

    async def run_test():
        manager = HAConfigurationManager()

        # Setup mock connection
        mock_connection = Mock()
        mock_connection.read_file = AsyncMock(return_value=content)
        manager._connections["test_instance"] = mock_connection

        # Mock file_saver
        save_result = SaveResult(
            local_path=f"/tmp/ha-dev-tools/{file_path}",
            file_size=len(content.encode("utf-8")),
            remote_path=file_path,
            checksum="a" * 64,
        )

        with patch.object(
            manager.file_saver, "save_file", new_callable=AsyncMock
        ) as mock_save:
            mock_save.return_value = save_result

            # Execute with save_local=True
            result = await manager.read_config_file(
                instance_id="test_instance", file_path=file_path, save_local=True
            )

            # Verify all required fields present
            assert result["saved"] is True
            assert "local_path" in result
            assert "file_size" in result
            assert "remote_path" in result

            # Verify all fields have non-empty values
            assert result["local_path"]  # Non-empty string
            assert result["file_size"] >= 0  # Non-negative number
            assert result["remote_path"]  # Non-empty string

            # Verify content field is NOT present
            assert "content" not in result

    asyncio.run(run_test())


@given(
    offset=st.one_of(st.integers(min_value=0, max_value=1000), st.none()),
    length=st.one_of(st.integers(min_value=1, max_value=1000), st.none()),
)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_mutually_exclusive_parameters(offset, length):
    """Property 10: Mutually Exclusive Parameters.

    For any request with save_local=True and offset or length,
    verify error is raised.
    """
    # Skip if both offset and length are None (no pagination)
    if offset is None and length is None:
        return

    async def run_test():
        manager = HAConfigurationManager()

        # Setup mock connection
        mock_connection = Mock()
        mock_connection.read_file = AsyncMock(return_value="test content")
        manager._connections["test_instance"] = mock_connection

        # Execute with save_local=True and pagination params
        with pytest.raises(ValueError) as exc_info:
            await manager.read_config_file(
                instance_id="test_instance",
                file_path="test.yaml",
                save_local=True,
                offset=offset,
                length=length,
            )

        # Verify error message mentions mutual exclusivity
        error_msg = str(exc_info.value).lower()
        assert "mutually exclusive" in error_msg or "exclusive" in error_msg

    asyncio.run(run_test())


@given(content=file_content_strategy)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_property_pagination_without_save_local(content):
    """Verify pagination works correctly when save_local is not used.

    This ensures backward compatibility with existing pagination feature.
    """
    # Only test with content that has at least 10 bytes
    if len(content.encode("utf-8")) < 10:
        return

    async def run_test():
        manager = HAConfigurationManager()

        # Setup mock connection
        mock_connection = Mock()
        mock_connection.read_file = AsyncMock(return_value=content)
        manager._connections["test_instance"] = mock_connection

        # Execute with pagination (no save_local)
        result = await manager.read_config_file(
            instance_id="test_instance", file_path="test.yaml", offset=0, length=5
        )

        # Verify pagination worked
        assert result["saved"] is False
        assert "content" in result
        # Content should be truncated to 5 bytes
        assert len(result["content"].encode("utf-8")) <= 5

    asyncio.run(run_test())
