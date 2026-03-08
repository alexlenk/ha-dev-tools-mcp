"""Basic unit tests for HAAPIClient class without HA test framework."""

import pytest
from ha_dev_tools.connection.api import HAAPIClient, HAAPIError


class TestHAAPIClientBasic:
    """Test HAAPIClient initialization and basic configuration."""

    def test_client_initialization(self):
        """Test that HAAPIClient initializes with correct parameters."""
        base_url = "http://homeassistant.local:8123"
        access_token = "test_token_123"

        client = HAAPIClient(base_url, access_token)

        # Verify attributes are set correctly
        assert client.base_url == "http://homeassistant.local:8123"
        assert client.access_token == "test_token_123"
        assert client.timeout == 30  # Default timeout
        # Session should not be created yet (lazy initialization)
        assert client._session is None

    def test_client_initialization_with_custom_timeout(self):
        """Test that HAAPIClient accepts custom timeout."""
        base_url = "http://homeassistant.local:8123"
        access_token = "test_token_123"
        timeout = 60

        client = HAAPIClient(base_url, access_token, timeout=timeout)

        assert client.timeout == 60

    def test_client_strips_trailing_slash_from_url(self):
        """Test that trailing slash is removed from base_url."""
        base_url = "http://homeassistant.local:8123/"
        access_token = "test_token_123"

        client = HAAPIClient(base_url, access_token)

        assert client.base_url == "http://homeassistant.local:8123"
        assert not client.base_url.endswith("/")

    def test_client_session_lazy_initialization(self):
        """Test that session is not created during initialization."""
        base_url = "http://homeassistant.local:8123"
        access_token = "test_token_123"

        client = HAAPIClient(base_url, access_token)

        # Session should not exist yet (lazy initialization)
        assert client._session is None


class TestHAAPIError:
    """Test HAAPIError exception class."""

    def test_api_error_initialization(self):
        """Test that HAAPIError initializes with correct attributes."""
        message = "File not found"
        status_code = 404
        error_code = "FILE_NOT_FOUND"

        error = HAAPIError(message, status_code, error_code)

        assert error.message == "File not found"
        assert error.status_code == 404
        assert error.error_code == "FILE_NOT_FOUND"
        assert str(error) == "File not found"

    def test_api_error_is_exception(self):
        """Test that HAAPIError is a proper Exception."""
        error = HAAPIError("Test error", 500, "TEST_ERROR")

        assert isinstance(error, Exception)

        # Test that it can be raised and caught
        with pytest.raises(HAAPIError) as exc_info:
            raise error

        assert exc_info.value.message == "Test error"
        assert exc_info.value.status_code == 500
        assert exc_info.value.error_code == "TEST_ERROR"


class TestErrorTranslation:
    """Test error translation from HTTP status codes to HAAPIError."""

    def test_translate_error_400_bad_request(self):
        """Test translation of 400 Bad Request errors."""
        client = HAAPIClient("http://ha.local:8123", "token")

        # Test with API error message
        response_text = '{"message": "Invalid parameter: file_path"}'
        error = client._translate_error(400, response_text)

        assert error.status_code == 400
        assert error.error_code == "INVALID_REQUEST"
        assert "Invalid request: Invalid parameter: file_path" in error.message

    def test_translate_error_400_without_message(self):
        """Test translation of 400 errors without API message."""
        client = HAAPIClient("http://ha.local:8123", "token")

        error = client._translate_error(400, "")

        assert error.status_code == 400
        assert error.error_code == "INVALID_REQUEST"
        assert "Invalid request parameters" in error.message

    def test_translate_error_401_unauthorized(self):
        """Test translation of 401 Unauthorized errors."""
        client = HAAPIClient("http://ha.local:8123", "token")

        error = client._translate_error(401)

        assert error.status_code == 401
        assert error.error_code == "AUTHENTICATION_FAILED"
        assert "Authentication failed" in error.message
        assert "HA_TOKEN" in error.message

    def test_translate_error_403_forbidden(self):
        """Test translation of 403 Forbidden errors."""
        client = HAAPIClient("http://ha.local:8123", "token")

        error = client._translate_error(403)

        assert error.status_code == 403
        assert error.error_code == "PERMISSION_DENIED"
        assert "Permission denied" in error.message
        assert "sufficient permissions" in error.message

    def test_translate_error_404_with_file_path(self):
        """Test translation of 404 errors with file path."""
        client = HAAPIClient("http://ha.local:8123", "token")

        error = client._translate_error(404, file_path="configuration.yaml")

        assert error.status_code == 404
        assert error.error_code == "FILE_NOT_FOUND"
        assert "File not found: configuration.yaml" in error.message

    def test_translate_error_404_without_file_path(self):
        """Test translation of 404 errors without file path."""
        client = HAAPIClient("http://ha.local:8123", "token")

        error = client._translate_error(404)

        assert error.status_code == 404
        assert error.error_code == "RESOURCE_NOT_FOUND"
        assert "Resource not found" in error.message

    def test_translate_error_500_internal_server_error(self):
        """Test translation of 500 Internal Server Error."""
        client = HAAPIClient("http://ha.local:8123", "token")

        error = client._translate_error(500)

        assert error.status_code == 500
        assert error.error_code == "SERVER_ERROR"
        assert "Home Assistant server error" in error.message
        assert "check HA logs" in error.message

    def test_translate_error_502_bad_gateway(self):
        """Test translation of 502 Bad Gateway errors."""
        client = HAAPIClient("http://ha.local:8123", "token")

        error = client._translate_error(502)

        assert error.status_code == 502
        assert error.error_code == "SERVICE_UNAVAILABLE"
        assert "Home Assistant instance is unavailable" in error.message

    def test_translate_error_503_service_unavailable(self):
        """Test translation of 503 Service Unavailable errors."""
        client = HAAPIClient("http://ha.local:8123", "token")

        error = client._translate_error(503)

        assert error.status_code == 503
        assert error.error_code == "SERVICE_UNAVAILABLE"
        assert "Home Assistant instance is unavailable" in error.message

    def test_translate_error_504_gateway_timeout(self):
        """Test translation of 504 Gateway Timeout errors."""
        client = HAAPIClient("http://ha.local:8123", "token")

        error = client._translate_error(504)

        assert error.status_code == 504
        assert error.error_code == "SERVICE_UNAVAILABLE"
        assert "Home Assistant instance is unavailable" in error.message

    def test_translate_error_unknown_status_code(self):
        """Test translation of unknown status codes."""
        client = HAAPIClient("http://ha.local:8123", "token")

        error = client._translate_error(418)  # I'm a teapot

        assert error.status_code == 418
        assert error.error_code == "UNKNOWN_ERROR"
        assert "HTTP 418 error" in error.message

    def test_translate_error_with_invalid_json(self):
        """Test translation when response contains invalid JSON."""
        client = HAAPIClient("http://ha.local:8123", "token")

        # Invalid JSON should be handled gracefully
        response_text = "This is not JSON"
        error = client._translate_error(400, response_text)

        assert error.status_code == 400
        assert error.error_code == "INVALID_REQUEST"
        # Should still create an error, even if JSON parsing fails


class TestNetworkErrorHandling:
    """Test network-level error handling."""

    def test_handle_timeout_error(self):
        """Test handling of connection timeout errors."""
        import asyncio

        client = HAAPIClient("http://ha.local:8123", "token", timeout=30)
        timeout_error = asyncio.TimeoutError()

        error = client._handle_network_error(timeout_error)

        assert error.status_code == 0
        assert error.error_code == "CONNECTION_TIMEOUT"
        assert "timed out after 30 seconds" in error.message
        assert "network connectivity" in error.message

    def test_handle_connection_error(self):
        """Test handling of connection failures."""
        import aiohttp

        client = HAAPIClient("http://ha.local:8123", "token")
        conn_error = aiohttp.ClientConnectionError("Connection refused")

        error = client._handle_network_error(
            conn_error, "http://ha.local:8123/api/states"
        )

        assert error.status_code == 0
        assert error.error_code == "CONNECTION_FAILED"
        assert "Cannot connect to Home Assistant" in error.message
        assert "http://ha.local:8123" in error.message

    def test_handle_json_decode_error(self):
        """Test handling of invalid JSON responses."""
        import json

        client = HAAPIClient("http://ha.local:8123", "token")
        json_error = json.JSONDecodeError("Expecting value", "doc", 0)

        error = client._handle_network_error(json_error)

        assert error.status_code == 0
        assert error.error_code == "INVALID_JSON_RESPONSE"
        assert "invalid JSON response" in error.message
        assert "unexpected" in error.message

    def test_handle_generic_client_error(self):
        """Test handling of generic aiohttp client errors."""
        import aiohttp

        client = HAAPIClient("http://ha.local:8123", "token")
        client_error = aiohttp.ClientError("Generic error")

        error = client._handle_network_error(client_error)

        assert error.status_code == 0
        assert error.error_code == "NETWORK_ERROR"
        assert "Network error" in error.message

    def test_handle_unknown_error(self):
        """Test handling of unknown error types."""
        client = HAAPIClient("http://ha.local:8123", "token")
        unknown_error = ValueError("Something went wrong")

        error = client._handle_network_error(unknown_error)

        assert error.status_code == 0
        assert error.error_code == "UNKNOWN_ERROR"
        assert "Unexpected error" in error.message


class TestSessionCleanup:
    """Test HTTP session cleanup functionality."""

    @pytest.mark.asyncio
    async def test_close_method_closes_session(self):
        """Test that close() method properly closes the aiohttp session."""
        client = HAAPIClient("http://ha.local:8123", "token")

        # Access session property to create it
        session = client.session
        assert session is not None
        assert not session.closed

        # Close the client
        await client.close()

        # Verify session is closed and cleared
        assert session.closed
        assert client._session is None

    @pytest.mark.asyncio
    async def test_close_method_handles_no_session(self):
        """Test that close() handles case when session was never created."""
        client = HAAPIClient("http://ha.local:8123", "token")

        # Session should not exist yet
        assert client._session is None

        # Close should not raise an error
        await client.close()

        # Session should still be None
        assert client._session is None

    @pytest.mark.asyncio
    async def test_close_method_handles_already_closed_session(self):
        """Test that close() handles case when session is already closed."""
        client = HAAPIClient("http://ha.local:8123", "token")

        # Create and close session
        session = client.session
        await session.close()

        # Close should not raise an error even though session is already closed
        await client.close()

        # Session should be cleared
        assert client._session is None

    @pytest.mark.asyncio
    async def test_session_can_be_recreated_after_close(self):
        """Test that a new session can be created after closing."""
        client = HAAPIClient("http://ha.local:8123", "token")

        # Create and close first session
        first_session = client.session
        await client.close()

        # Create new session
        second_session = client.session

        # Should be a different session object
        assert second_session is not first_session
        assert not second_session.closed

        # Clean up
        await client.close()
