"""Unit tests for query parameter construction."""

import pytest
from aioresponses import aioresponses
from ha_dev_tools.connection.api import HAAPIClient


class TestQueryParameterConstruction:
    """Tests for query parameter construction in API methods."""

    @pytest.mark.asyncio
    async def test_list_files_directory_parameter(self):
        """Test that directory parameter is properly included in list_files query."""
        client = HAAPIClient("http://ha.local:8123", "test_token")

        with aioresponses() as m:
            # Mock the request and capture the URL
            m.get(
                "http://ha.local:8123/api/management/files?directory=packages",
                status=200,
                body='{"files": [], "directory": "packages"}',
            )

            result = await client.list_files(directory="packages")

            # Verify the request was made with the correct query parameter
            assert result is not None

        await client.close()

    @pytest.mark.asyncio
    async def test_list_files_without_directory_parameter(self):
        """Test that list_files works without directory parameter."""
        client = HAAPIClient("http://ha.local:8123", "test_token")

        with aioresponses() as m:
            # Mock the request without directory parameter
            m.get(
                "http://ha.local:8123/api/management/files",
                status=200,
                body='{"files": [], "directory": ""}',
            )

            result = await client.list_files()

            assert result is not None

        await client.close()

    @pytest.mark.asyncio
    async def test_list_files_empty_directory_parameter(self):
        """Test that empty directory parameter is handled correctly."""
        client = HAAPIClient("http://ha.local:8123", "test_token")

        with aioresponses() as m:
            # Empty directory should result in no query parameter
            m.get(
                "http://ha.local:8123/api/management/files",
                status=200,
                body='{"files": [], "directory": ""}',
            )

            result = await client.list_files(directory="")

            assert result is not None

        await client.close()

    @pytest.mark.asyncio
    async def test_get_logs_all_filter_parameters(self):
        """Test that all log filter parameters are properly included in get_logs query."""
        client = HAAPIClient("http://ha.local:8123", "test_token")

        with aioresponses() as m:
            # Mock with all filter parameters
            m.get(
                "http://ha.local:8123/api/management/logs/core?lines=50&level=ERROR&search=timeout&offset=10&limit=25",
                status=200,
                body='{"logs": [], "total_count": 0, "source": "core"}',
            )

            result = await client.get_logs(
                log_source="core",
                lines=50,
                level="ERROR",
                search="timeout",
                offset=10,
                limit=25,
            )

            assert result is not None

        await client.close()

    @pytest.mark.asyncio
    async def test_get_logs_default_parameters(self):
        """Test that get_logs uses default parameters when not specified."""
        client = HAAPIClient("http://ha.local:8123", "test_token")

        with aioresponses() as m:
            # Default parameters: lines=100, offset=0, limit=100
            m.get(
                "http://ha.local:8123/api/management/logs/core?lines=100&offset=0&limit=100",
                status=200,
                body='{"logs": [], "total_count": 0, "source": "core"}',
            )

            result = await client.get_logs(log_source="core")

            assert result is not None

        await client.close()

    @pytest.mark.asyncio
    async def test_get_logs_partial_parameters(self):
        """Test that get_logs works with partial filter parameters."""
        client = HAAPIClient("http://ha.local:8123", "test_token")

        with aioresponses() as m:
            # Only level and search specified
            m.get(
                "http://ha.local:8123/api/management/logs/core?lines=100&level=WARNING&search=error&offset=0&limit=100",
                status=200,
                body='{"logs": [], "total_count": 0, "source": "core"}',
            )

            result = await client.get_logs(
                log_source="core", level="WARNING", search="error"
            )

            assert result is not None

        await client.close()

    @pytest.mark.asyncio
    async def test_get_history_all_parameters(self):
        """Test that all history filter parameters are properly included in get_history query."""
        client = HAAPIClient("http://ha.local:8123", "test_token")

        with aioresponses() as m:
            # Mock with all parameters - start_time is appended to URL path
            m.get(
                "http://ha.local:8123/api/history/period/2024-01-15T10:00:00?end_time=2024-01-15T11:00:00&filter_entity_id=sensor.temperature,light.living_room",
                status=200,
                body="[[]]",
            )

            result = await client.get_history(
                start_time="2024-01-15T10:00:00",
                end_time="2024-01-15T11:00:00",
                entity_ids=["sensor.temperature", "light.living_room"],
            )

            assert result is not None

        await client.close()

    @pytest.mark.asyncio
    async def test_get_history_without_parameters(self):
        """Test that get_history works without any parameters."""
        client = HAAPIClient("http://ha.local:8123", "test_token")

        with aioresponses() as m:
            # No query parameters
            m.get("http://ha.local:8123/api/history/period", status=200, body="[[]]")

            result = await client.get_history()

            assert result is not None

        await client.close()

    @pytest.mark.asyncio
    async def test_get_history_with_start_time_only(self):
        """Test that get_history works with only start_time parameter."""
        client = HAAPIClient("http://ha.local:8123", "test_token")

        with aioresponses() as m:
            # start_time is appended to URL path, no query parameters
            m.get(
                "http://ha.local:8123/api/history/period/2024-01-15T10:00:00",
                status=200,
                body="[[]]",
            )

            result = await client.get_history(start_time="2024-01-15T10:00:00")

            assert result is not None

        await client.close()

    @pytest.mark.asyncio
    async def test_get_history_with_entity_ids_only(self):
        """Test that get_history works with only entity_ids parameter."""
        client = HAAPIClient("http://ha.local:8123", "test_token")

        with aioresponses() as m:
            m.get(
                "http://ha.local:8123/api/history/period?filter_entity_id=sensor.temperature",
                status=200,
                body="[[]]",
            )

            result = await client.get_history(entity_ids=["sensor.temperature"])

            assert result is not None

        await client.close()

    @pytest.mark.asyncio
    async def test_get_history_with_multiple_entity_ids(self):
        """Test that multiple entity IDs are properly formatted in query."""
        client = HAAPIClient("http://ha.local:8123", "test_token")

        with aioresponses() as m:
            # Multiple entity IDs should be comma-separated
            m.get(
                "http://ha.local:8123/api/history/period?filter_entity_id=sensor.temp1,sensor.temp2,sensor.temp3",
                status=200,
                body="[[]]",
            )

            result = await client.get_history(
                entity_ids=["sensor.temp1", "sensor.temp2", "sensor.temp3"]
            )

            assert result is not None

        await client.close()

    @pytest.mark.asyncio
    async def test_query_parameters_with_special_characters(self):
        """Test that special characters in query parameters are properly encoded."""
        client = HAAPIClient("http://ha.local:8123", "test_token")

        with aioresponses() as m:
            # Search term with spaces and special characters
            m.get(
                "http://ha.local:8123/api/management/logs/core?lines=100&search=error%3A%20timeout&offset=0&limit=100",
                status=200,
                body='{"logs": [], "total_count": 0, "source": "core"}',
            )

            result = await client.get_logs(log_source="core", search="error: timeout")

            assert result is not None

        await client.close()
