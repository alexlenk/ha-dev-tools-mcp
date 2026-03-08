"""API-based Home Assistant connection implementation."""

import asyncio
import gzip
import hashlib
import json
from typing import Dict, List, Optional, Any, Union
from urllib.parse import urljoin

import aiohttp

from ..types import HAConnection, ConnectionError


class HAAPIError(Exception):
    """Base exception for Home Assistant API errors.
    
    Attributes:
        message: Human-readable error message
        status_code: HTTP status code from the API response
        error_code: Application-specific error code for categorization
    """
    
    def __init__(self, message: str, status_code: int, error_code: str):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code


class HAAPIClient:
    """HTTP client for Home Assistant REST API.
    
    This client provides a simple interface for making authenticated requests
    to both the custom HA Config Manager integration API and the official
    Home Assistant REST API.
    
    The client handles:
    - Authentication via Bearer token
    - Proper HTTP headers (Authorization, Content-Type)
    - Request timeouts
    - SSL certificate verification
    - Error translation from HTTP responses to application errors
    
    Attributes:
        base_url: Home Assistant instance URL (without trailing slash)
        access_token: Long-lived access token for authentication
        timeout: Request timeout in seconds (default: 30)
        session: aiohttp ClientSession for making requests
    
    Example:
        >>> client = HAAPIClient("http://homeassistant.local:8123", "token123")
        >>> files = await client.list_files()
        >>> content = await client.read_file("configuration.yaml")
        >>> await client.close()
    """
    
    def __init__(self, base_url: str, access_token: str, timeout: int = 30):
        """Initialize the API client.
        
        Args:
            base_url: Home Assistant instance URL (e.g., "http://homeassistant.local:8123")
            access_token: Long-lived access token for authentication
            timeout: Request timeout in seconds (default: 30)
        """
        self.base_url = base_url.rstrip('/')
        self.access_token = access_token
        self.timeout = timeout
        self._session: Optional[aiohttp.ClientSession] = None
    
    @property
    def session(self) -> aiohttp.ClientSession:
        """Get or create the aiohttp ClientSession.
        
        The session is created lazily on first access to ensure it's created
        within an async context with a running event loop.
        
        Returns:
            aiohttp.ClientSession configured with proper headers and timeout
        """
        if self._session is None or self._session.closed:
            timeout_config = aiohttp.ClientTimeout(total=self.timeout)
            self._session = aiohttp.ClientSession(
                timeout=timeout_config,
                headers={
                    'Authorization': f'Bearer {self.access_token}',
                    'Content-Type': 'application/json'
                }
            )
        return self._session
    
    async def close(self):
        """Close the HTTP session and clean up resources.
        
        This should be called when the client is no longer needed to ensure
        proper cleanup of the aiohttp session.
        """
        if self._session:
            if not self._session.closed:
                await self._session.close()
            self._session = None
    
    def _translate_error(
        self, 
        status_code: int, 
        response_text: str = "", 
        url: str = "",
        file_path: str = ""
    ) -> HAAPIError:
        """Translate HTTP status codes to user-friendly error messages.
        
        Maps HTTP error responses to application-specific error codes and
        provides clear, actionable error messages for users.
        
        Args:
            status_code: HTTP status code from the response
            response_text: Response body text (may contain API error details)
            url: The URL that was requested (for context in error messages)
            file_path: File path if applicable (for file-specific errors)
        
        Returns:
            HAAPIError with appropriate message, status_code, and error_code
        
        Error Code Mapping:
            400 -> INVALID_REQUEST: Validation errors
            401 -> AUTHENTICATION_FAILED: Invalid/expired token
            403 -> PERMISSION_DENIED: Insufficient permissions
            404 -> FILE_NOT_FOUND or RESOURCE_NOT_FOUND: Resource not found
            500 -> SERVER_ERROR: Internal server error
            502/503/504 -> SERVICE_UNAVAILABLE: Service unavailable
        """
        # Try to extract error message from API response
        api_error_message = ""
        try:
            if response_text:
                error_data = json.loads(response_text)
                api_error_message = error_data.get("message", "")
        except (json.JSONDecodeError, KeyError):
            # If we can't parse JSON or find message, use raw response
            api_error_message = response_text[:200] if response_text else ""
        
        # Map status codes to error codes and messages
        if status_code == 400:
            # Bad Request - validation errors
            message = f"Invalid request: {api_error_message}" if api_error_message else "Invalid request parameters"
            return HAAPIError(message, status_code, "INVALID_REQUEST")
        
        elif status_code == 401:
            # Unauthorized - invalid or expired token
            message = "Authentication failed. Please check your HA_TOKEN is valid and not expired."
            return HAAPIError(message, status_code, "AUTHENTICATION_FAILED")
        
        elif status_code == 403:
            # Forbidden - insufficient permissions
            message = "Permission denied. Your token does not have sufficient permissions."
            return HAAPIError(message, status_code, "PERMISSION_DENIED")
        
        elif status_code == 404:
            # Not Found - file or resource doesn't exist
            if file_path:
                message = f"File not found: {file_path}"
                error_code = "FILE_NOT_FOUND"
            else:
                message = "Resource not found"
                error_code = "RESOURCE_NOT_FOUND"
            return HAAPIError(message, status_code, error_code)
        
        elif status_code == 409:
            # Conflict - version conflict detected
            message = f"Version conflict: File has been modified since last read. {api_error_message}" if api_error_message else "Version conflict: File has been modified"
            return HAAPIError(message, status_code, "VERSION_CONFLICT")
        
        elif status_code == 500:
            # Internal Server Error
            message = "Home Assistant server error occurred. Please check HA logs."
            return HAAPIError(message, status_code, "SERVER_ERROR")
        
        elif status_code in (502, 503, 504):
            # Service Unavailable - HA instance is down or unreachable
            message = "Home Assistant instance is unavailable. Please check if HA is running."
            return HAAPIError(message, status_code, "SERVICE_UNAVAILABLE")
        
        else:
            # Unknown error code
            message = f"HTTP {status_code} error"
            if api_error_message:
                message += f": {api_error_message}"
            return HAAPIError(message, status_code, "UNKNOWN_ERROR")
    
    async def _handle_response_errors(
        self,
        response: aiohttp.ClientResponse,
        file_path: str = ""
    ) -> None:
        """Check response status and raise HAAPIError if not successful.
        
        Args:
            response: aiohttp response object
            file_path: Optional file path for context in error messages
        
        Raises:
            HAAPIError: If response status indicates an error (4xx or 5xx)
        """
        if response.status >= 400:
            response_text = await response.text()
            error = self._translate_error(
                response.status,
                response_text,
                str(response.url),
                file_path
            )
            raise error
    
    def _handle_network_error(self, error: Exception, url: str = "") -> HAAPIError:
        """Translate network-level exceptions to HAAPIError.
        
        Handles connection timeouts, connection failures, and other network errors
        that occur before receiving an HTTP response.
        
        Args:
            error: The exception that was raised
            url: The URL that was being accessed (for context)
        
        Returns:
            HAAPIError with appropriate message and error code
        """
        if isinstance(error, asyncio.TimeoutError):
            # Connection timeout
            message = f"Request timed out after {self.timeout} seconds. Check network connectivity."
            return HAAPIError(message, 0, "CONNECTION_TIMEOUT")
        
        elif isinstance(error, aiohttp.ClientConnectionError):
            # Connection failed - HA instance unreachable
            url_display = url or self.base_url
            message = f"Cannot connect to Home Assistant at {url_display}. Check URL and network."
            return HAAPIError(message, 0, "CONNECTION_FAILED")
        
        elif isinstance(error, aiohttp.ClientError):
            # Other aiohttp client errors
            message = f"Network error: {str(error)}"
            return HAAPIError(message, 0, "NETWORK_ERROR")
        
        elif isinstance(error, json.JSONDecodeError):
            # Invalid JSON response
            message = "Received invalid JSON response from Home Assistant. The response format was unexpected."
            return HAAPIError(message, 0, "INVALID_JSON_RESPONSE")
        
        else:
            # Unknown error
            message = f"Unexpected error: {str(error)}"
            return HAAPIError(message, 0, "UNKNOWN_ERROR")
    async def list_files(self, directory: str = "") -> List[Dict[str, Any]]:
        """List configuration files from Home Assistant.

        Makes a GET request to /api/ha_config_manager/files to retrieve
        the list of available configuration files.

        Args:
            directory: Optional directory to filter files (e.g., 'packages')

        Returns:
            List of file objects with metadata (path, type, size, last_modified)

        Raises:
            HAAPIError: If the API request fails or returns an error

        Example:
            >>> files = await client.list_files()
            >>> [{'path': 'configuration.yaml', 'type': 'configuration', ...}]

            >>> package_files = await client.list_files(directory='packages')
        """
        url = f"{self.base_url}/api/management/files"

        # Build query parameters
        params = {}
        if directory:
            params['directory'] = directory

        try:
            async with self.session.get(url, params=params) as response:
                # Check for HTTP errors
                await self._handle_response_errors(response)

                # Parse JSON response
                data = await response.json()

                # Return the file list
                return data.get('files', [])

        except HAAPIError:
            # Re-raise HAAPIError as-is
            raise
        except Exception as e:
            # Translate network errors to HAAPIError
            raise self._handle_network_error(e, url)
    async def read_file(
        self,
        file_path: str,
        offset: int = 0,
        limit: Optional[int] = None,
        compress: bool = False
    ) -> Dict[str, Any]:
        """Read configuration file content from Home Assistant with chunking support.

        Makes a GET request to /api/ha_config_manager/files/{file_path} to
        retrieve the content of a specific configuration file. Supports pagination
        for large files and optional compression.

        Args:
            file_path: Path to the configuration file (e.g., 'configuration.yaml')
            offset: Byte offset to start reading from (default: 0)
            limit: Maximum bytes to return (default: None = no limit)
            compress: Whether to request gzip compression (default: False)

        Returns:
            Dictionary containing:
                - content: File content as plain text string
                - metadata: Dictionary with:
                    - total_size: Total file size in bytes
                    - returned_size: Size of content returned in this response
                    - truncated: Whether content was truncated
                    - offset: Byte offset of this chunk
                    - has_more: Whether more content is available
                    - compressed: Whether content was compressed
                    - content_hash: SHA256 hash of the content

        Raises:
            HAAPIError: If the file doesn't exist (404), access is denied (403),
                       or other API errors occur

        Example:
            >>> result = await client.read_file('configuration.yaml')
            >>> print(result['content'])
            homeassistant:
              name: Home
              ...
            >>> print(result['metadata']['total_size'])
            1024
            
            >>> # Read large file in chunks
            >>> chunk1 = await client.read_file('large.yaml', offset=0, limit=100000)
            >>> if chunk1['metadata']['has_more']:
            ...     chunk2 = await client.read_file('large.yaml', offset=100000, limit=100000)
        """
        # Construct URL with file path
        url = f"{self.base_url}/api/management/files/{file_path}"
        
        # Build query parameters
        params = {}
        if offset > 0:
            params['offset'] = offset
        if limit is not None:
            params['limit'] = limit
        if compress:
            params['compress'] = 'true'

        try:
            async with self.session.get(url, params=params) as response:
                # Check for HTTP errors (404, 403, etc.)
                await self._handle_response_errors(response, file_path=file_path)

                # Get metadata from headers
                content_length = response.headers.get('Content-Length')
                total_size_header = response.headers.get('X-Total-Size')
                offset_header = response.headers.get('X-Offset', str(offset))
                has_more_header = response.headers.get('X-Has-More', 'false')
                
                # Read response body
                if compress and response.headers.get('Content-Encoding') == 'gzip':
                    # Decompress gzip content
                    compressed_content = await response.read()
                    content = gzip.decompress(compressed_content).decode('utf-8')
                else:
                    content = await response.text()
                
                # Calculate sizes
                returned_size = len(content.encode('utf-8'))
                total_size = int(total_size_header) if total_size_header else returned_size
                
                # Determine if content was truncated
                truncated = returned_size < total_size
                has_more = has_more_header.lower() == 'true' or truncated
                
                # Calculate content hash
                content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
                
                # Build metadata
                metadata = {
                    'total_size': total_size,
                    'returned_size': returned_size,
                    'truncated': truncated,
                    'offset': int(offset_header),
                    'has_more': has_more,
                    'compressed': compress and response.headers.get('Content-Encoding') == 'gzip',
                    'content_hash': content_hash
                }
                
                return {
                    'content': content,
                    'metadata': metadata
                }

        except HAAPIError:
            # Re-raise HAAPIError as-is
            raise
        except Exception as e:
            # Translate network errors to HAAPIError
            raise self._handle_network_error(e, url)

    async def write_file(
        self,
        file_path: str,
        content: str,
        expected_hash: Optional[str] = None,
        validate_before_write: bool = True
    ) -> Dict[str, Any]:
        """Write content to a configuration file on Home Assistant.

        Makes a PUT request to /api/ha_config_manager/files/{file_path} to
        write content to a configuration file. Supports YAML validation and
        conflict detection via expected_hash.

        Args:
            file_path: Path to the configuration file (e.g., 'configuration.yaml')
            content: File content to write
            expected_hash: Expected current hash for conflict detection (optional).
                          If provided, write will fail if file has been modified.
            validate_before_write: Validate YAML syntax before writing (default: True)

        Returns:
            Dictionary containing new file metadata after write:
                - path: str - File path
                - size: int - File size in bytes
                - modified_at: str - ISO 8601 timestamp
                - content_hash: str - SHA-256 hash of new content
                - success: bool - Whether write succeeded

        Raises:
            HAAPIError: If validation fails, hash conflict detected (409),
                       access is denied (403), or other API errors occur

        Example:
            >>> metadata = await client.write_file(
            ...     'automations.yaml',
            ...     'automation:\\n  - alias: Test\\n',
            ...     expected_hash='abc123'
            ... )
            >>> print(f"Written: {metadata['size']} bytes, hash: {metadata['content_hash']}")
        """
        # Construct URL with file path
        url = f"{self.base_url}/api/management/files/{file_path}"

        # Prepare request body
        request_body = {
            "content": content,
            "validate_before_write": validate_before_write
        }
        
        if expected_hash:
            request_body["expected_hash"] = expected_hash

        try:
            async with self.session.put(url, json=request_body) as response:
                # Check for HTTP errors (409 for conflict, 403, etc.)
                await self._handle_response_errors(response, file_path=file_path)

                # Return response body as JSON with metadata
                return await response.json()

        except HAAPIError:
            # Re-raise HAAPIError as-is
            raise
        except Exception as e:
            # Translate network errors to HAAPIError
            raise self._handle_network_error(e, url)

    async def get_file_metadata(self, file_path: str) -> Dict[str, Any]:
        """Get metadata for a configuration file without reading content.

        Makes a GET request to /api/ha_config_manager/metadata/{file_path} to
        retrieve metadata including path, size, modification timestamp, and content hash.

        Args:
            file_path: Path to the configuration file (e.g., 'configuration.yaml')

        Returns:
            Dictionary containing:
                - path: str - File path
                - size: int - File size in bytes
                - modified_at: str - ISO 8601 timestamp
                - content_hash: str - SHA-256 hash
                - exists: bool - Whether file exists
                - accessible: bool - Whether file is accessible

        Raises:
            HAAPIError: If the file doesn't exist (404), access is denied (403),
                       or other API errors occur

        Example:
            >>> metadata = await client.get_file_metadata('configuration.yaml')
            >>> print(f"Size: {metadata['size']}, Hash: {metadata['content_hash']}")
        """
        # Construct URL with file path
        url = f"{self.base_url}/api/management/metadata/{file_path}"

        try:
            async with self.session.get(url) as response:
                # Check for HTTP errors (404, 403, etc.)
                await self._handle_response_errors(response, file_path=file_path)

                # Return response body as JSON
                return await response.json()

        except HAAPIError:
            # Re-raise HAAPIError as-is
            raise
        except Exception as e:
            # Translate network errors to HAAPIError
            raise self._handle_network_error(e, url)

    async def batch_get_metadata(self, file_paths: List[str]) -> List[Dict[str, Any]]:
        """Get metadata for multiple configuration files in one request.

        Makes a POST request to /api/ha_config_manager/metadata/batch with
        an array of file paths to retrieve metadata for all files efficiently.

        Args:
            file_paths: List of file paths (e.g., ['configuration.yaml', 'automations.yaml'])

        Returns:
            List of metadata dictionaries, one for each file. Each dictionary contains:
                - path: str - File path
                - size: int - File size in bytes (or None if error)
                - modified_at: str - ISO 8601 timestamp (or None if error)
                - content_hash: str - SHA-256 hash (or None if error)
                - exists: bool - Whether file exists
                - accessible: bool - Whether file is accessible
                - error: str - Error message if file couldn't be accessed (optional)

        Raises:
            HAAPIError: If the request fails or other API errors occur

        Example:
            >>> metadata_list = await client.batch_get_metadata(['configuration.yaml', 'automations.yaml'])
            >>> for meta in metadata_list:
            ...     print(f"{meta['path']}: {meta['size']} bytes")
        """
        # Construct URL for batch endpoint
        url = f"{self.base_url}/api/management/metadata/batch"

        try:
            # Send POST request with file paths in body
            async with self.session.post(url, json={"file_paths": file_paths}) as response:
                # Check for HTTP errors
                await self._handle_response_errors(response)

                # Return response body as JSON array
                return await response.json()

        except HAAPIError:
            # Re-raise HAAPIError as-is
            raise
        except Exception as e:
            # Translate network errors to HAAPIError
            raise self._handle_network_error(e, url)

    async def get_logs(
        self,
        log_source: str,
        lines: int = 100,
        level: Optional[str] = None,
        search: Optional[str] = None,
        offset: int = 0,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Retrieve Home Assistant logs with optional filtering.

        Makes a GET request to /api/ha_config_manager/logs/{log_source} to
        retrieve log entries with optional filtering by level, search term,
        and pagination.

        Args:
            log_source: Log source to retrieve (e.g., 'core')
            lines: Number of log lines to retrieve (default: 100)
            level: Filter by log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            search: Search term to filter log messages
            offset: Offset for pagination (default: 0)
            limit: Maximum number of entries to return (default: 100)

        Returns:
            List of log entry objects with timestamp, level, message, logger

        Raises:
            HAAPIError: If the log source is invalid or other API errors occur

        Example:
            >>> logs = await client.get_logs('core', level='ERROR', limit=50)
            >>> for log in logs:
            ...     print(f"{log['timestamp']} - {log['level']}: {log['message']}")
        """
        # Construct URL with log source
        url = f"{self.base_url}/api/management/logs/{log_source}"

        # Build query parameters from filter arguments
        params = {
            'lines': lines,
            'offset': offset,
            'limit': limit
        }

        if level:
            params['level'] = level

        if search:
            params['search'] = search

        try:
            async with self.session.get(url, params=params) as response:
                # Check for HTTP errors (invalid log source, etc.)
                await self._handle_response_errors(response)

                # Parse JSON response
                data = await response.json()

                # Return log entries
                return data.get('logs', [])

        except HAAPIError:
            # Re-raise HAAPIError as-is
            raise
        except Exception as e:
            # Translate network errors to HAAPIError
            raise self._handle_network_error(e, url)

    async def get_states(self, entity_id: Optional[str] = None) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """Get entity states from Home Assistant.

        Makes a GET request to /api/states (all entities) or /api/states/{entity_id}
        (single entity) to retrieve entity state information.

        Args:
            entity_id: Optional entity ID to get specific entity state (e.g., 'light.living_room')
                      If None, returns all entity states.

        Returns:
            If entity_id is provided: Single entity state dict with entity_id, state, 
                                     attributes, last_changed, last_updated
            If entity_id is None: List of all entity state dicts

        Raises:
            HAAPIError: If the entity doesn't exist (404) or other API errors occur

        Example:
            >>> # Get all entity states
            >>> all_states = await client.get_states()
            >>> print(len(all_states))
            42

            >>> # Get specific entity state
            >>> light_state = await client.get_states('light.living_room')
            >>> print(light_state['state'])
            'on'
        """
        # Construct URL based on whether entity_id is provided
        if entity_id:
            url = f"{self.base_url}/api/states/{entity_id}"
        else:
            url = f"{self.base_url}/api/states"

        try:
            async with self.session.get(url) as response:
                # Check for HTTP errors (404 for non-existent entity, etc.)
                await self._handle_response_errors(response)

                # Parse JSON response and return entity state data
                return await response.json()

        except HAAPIError:
            # Re-raise HAAPIError as-is
            raise
        except Exception as e:
            # Translate network errors to HAAPIError
            raise self._handle_network_error(e, url)

    async def call_service(
        self,
        domain: str,
        service: str,
        service_data: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Call a Home Assistant service to control devices or trigger actions.

        Makes a POST request to /api/services/{domain}/{service} to execute
        a service call with optional service data.

        Args:
            domain: Service domain (e.g., 'light', 'switch', 'automation')
            service: Service name (e.g., 'turn_on', 'turn_off', 'toggle')
            service_data: Optional service data/parameters (e.g., {'entity_id': 'light.living_room', 'brightness': 255})

        Returns:
            List of affected entity states after the service call

        Raises:
            HAAPIError: If the service doesn't exist (404) or other API errors occur

        Example:
            >>> # Turn on a light
            >>> states = await client.call_service('light', 'turn_on', {'entity_id': 'light.living_room'})
            >>> print(states[0]['state'])
            'on'

            >>> # Call service without data
            >>> await client.call_service('homeassistant', 'restart')
        """
        # Construct URL with domain and service
        url = f"{self.base_url}/api/services/{domain}/{service}"

        try:
            # Prepare request body (empty dict if no service_data provided)
            json_data = service_data if service_data is not None else {}

            async with self.session.post(url, json=json_data) as response:
                # Check for HTTP errors (404 for non-existent service, etc.)
                await self._handle_response_errors(response)

                # Parse JSON response and return affected entity states
                return await response.json()

        except HAAPIError:
            # Re-raise HAAPIError as-is
            raise
        except Exception as e:
            # Translate network errors to HAAPIError
            raise self._handle_network_error(e, url)

    async def render_template(self, template: str, validate_entities: bool = False) -> Union[str, Dict[str, Any]]:
        """Render a Jinja2 template with Home Assistant context and enhanced error reporting.

        Makes a POST request to /api/template to render a template string
        with access to Home Assistant states and functions. Optionally validates
        entity references before rendering.

        Args:
            template: Jinja2 template string to render (e.g., '{{ states("sensor.temperature") }}')
            validate_entities: If True, validate entity references before rendering (default: False)

        Returns:
            If successful without warnings: Rendered template output as a string
            If successful with warnings: Dict with 'result' and 'warnings' keys

        Raises:
            HAAPIError: If the template has syntax errors or other API errors occur

        Example:
            >>> result = await client.render_template('{{ states("sensor.temperature") }}')
            >>> print(result)
            '22.5'
            
            >>> result = await client.render_template('{{ states("sensor.invalid") }}', validate_entities=True)
            >>> print(result)
            {'result': 'unknown', 'warnings': 'Warning: The following entity does not exist: sensor.invalid'}
        """
        from ..template_validator import extract_entity_references, format_entity_validation_warnings
        
        warnings = []
        
        # Entity validation if requested
        if validate_entities:
            entity_ids = extract_entity_references(template)
            if entity_ids:
                existing, missing = await self.validate_entities(entity_ids)
                if missing:
                    warning_msg = format_entity_validation_warnings(missing)
                    warnings.append(warning_msg)
        
        url = f"{self.base_url}/api/template"

        try:
            # Send template in request body
            json_data = {'template': template}

            async with self.session.post(url, json=json_data) as response:
                # Check for HTTP errors (template syntax errors, etc.)
                await self._handle_response_errors(response)

                # Get rendered output as plain text
                result = await response.text()
                
                # Return result with warnings if applicable
                if warnings:
                    return {
                        "result": result,
                        "warnings": "\n".join(warnings)
                    }
                return result

        except HAAPIError:
            # Re-raise HAAPIError as-is
            raise
        except Exception as e:
            # Translate network errors to HAAPIError
            raise self._handle_network_error(e, url)

    async def validate_entities(self, entity_ids: List[str]) -> tuple[List[str], List[str]]:
        """Validate that entity IDs exist in Home Assistant.

        Queries the /api/states endpoint to retrieve all entity states,
        then partitions the input entity_ids into existing and missing entities.

        Args:
            entity_ids: List of entity IDs to validate (e.g., ['sensor.temperature', 'light.living_room'])

        Returns:
            Tuple of (existing_entities, missing_entities) as lists
            - existing_entities: Entity IDs that exist in Home Assistant
            - missing_entities: Entity IDs that do not exist in Home Assistant

        Raises:
            HAAPIError: If the API request fails

        Example:
            >>> existing, missing = await client.validate_entities(['sensor.temp', 'sensor.invalid'])
            >>> print(f"Existing: {existing}")
            ['sensor.temp']
            >>> print(f"Missing: {missing}")
            ['sensor.invalid']
        """
        url = f"{self.base_url}/api/states"

        try:
            async with self.session.get(url) as response:
                # Check for HTTP errors
                await self._handle_response_errors(response)

                # Parse JSON response to get all entity states
                all_states = await response.json()

                # Extract entity IDs from state objects
                available_entity_ids = {state['entity_id'] for state in all_states}

                # Partition input entity_ids into existing and missing
                existing_entities = [eid for eid in entity_ids if eid in available_entity_ids]
                missing_entities = [eid for eid in entity_ids if eid not in available_entity_ids]

                return (existing_entities, missing_entities)

        except HAAPIError:
            # Re-raise HAAPIError as-is
            raise
        except Exception as e:
            # Translate network errors to HAAPIError
            raise self._handle_network_error(e, url)


    async def get_history(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        entity_ids: Optional[List[str]] = None
    ) -> List[List[Dict[str, Any]]]:
        """Get historical state data for entities over a time period.

        Makes a GET request to /api/history/period to retrieve historical
        state changes for entities.

        Args:
            start_time: Start time in ISO 8601 format (e.g., '2024-01-15T10:00:00'). Defaults to 1 day ago.
            end_time: End time in ISO 8601 format. Defaults to now.
            entity_ids: List of entity IDs to get history for. If omitted, returns history for all entities.

        Returns:
            List of lists containing historical state data with timestamps for each state change

        Raises:
            HAAPIError: If API errors occur

        Example:
            >>> history = await client.get_history(
            ...     start_time='2024-01-15T10:00:00',
            ...     entity_ids=['sensor.temperature']
            ... )
            >>> for state in history[0]:
            ...     print(f"{state['last_changed']}: {state['state']}")
        """
        url = f"{self.base_url}/api/history/period"

        # Build query parameters
        params = {}
        if start_time:
            # Append start_time to URL path
            url = f"{url}/{start_time}"
            # Only add filter_entity_id if entity_ids is provided
            if entity_ids:
                params['filter_entity_id'] = ','.join(entity_ids)
        
        if end_time:
            params['end_time'] = end_time
        
        if entity_ids and not start_time:
            params['filter_entity_id'] = ','.join(entity_ids)

        try:
            async with self.session.get(url, params=params) as response:
                # Check for HTTP errors
                await self._handle_response_errors(response)

                # Parse JSON response and return historical state data
                return await response.json()

        except HAAPIError:
            # Re-raise HAAPIError as-is
            raise
        except Exception as e:
            # Translate network errors to HAAPIError
            raise self._handle_network_error(e, url)

    async def get_config(self) -> Dict[str, Any]:
        """Get Home Assistant configuration details.

        Makes a GET request to /api/config to retrieve configuration
        information including version, location, unit system, time zone, and components.

        Returns:
            Configuration data dict with version, location, unit_system, time_zone, components, etc.

        Raises:
            HAAPIError: If API errors occur

        Example:
            >>> config = await client.get_config()
            >>> print(config['version'])
            '2024.1.0'
            >>> print(config['time_zone'])
            'America/Los_Angeles'
        """
        url = f"{self.base_url}/api/config"

        try:
            async with self.session.get(url) as response:
                # Check for HTTP errors
                await self._handle_response_errors(response)

                # Parse JSON response and return configuration data
                return await response.json()

        except HAAPIError:
            # Re-raise HAAPIError as-is
            raise
        except Exception as e:
            # Translate network errors to HAAPIError
            raise self._handle_network_error(e, url)

    async def list_events(self) -> List[Dict[str, Any]]:
        """List all available event types in Home Assistant.

        Makes a GET request to /api/events to retrieve the list of
        event types with their listener counts.

        Returns:
            List of event objects with event type and listener count

        Raises:
            HAAPIError: If API errors occur

        Example:
            >>> events = await client.list_events()
            >>> for event in events:
            ...     print(f"{event['event']}: {event['listener_count']} listeners")
        """
        url = f"{self.base_url}/api/events"

        try:
            async with self.session.get(url) as response:
                # Check for HTTP errors
                await self._handle_response_errors(response)

                # Parse JSON response and return event list
                return await response.json()

        except HAAPIError:
            # Re-raise HAAPIError as-is
            raise
        except Exception as e:
            # Translate network errors to HAAPIError
            raise self._handle_network_error(e, url)

    async def list_services(self) -> Dict[str, Any]:
        """List all available services organized by domain.

        Makes a GET request to /api/services to retrieve services
        with descriptions and field schemas.

        Returns:
            Dict of services organized by domain with descriptions and field information

        Raises:
            HAAPIError: If API errors occur

        Example:
            >>> services = await client.list_services()
            >>> for domain, domain_services in services.items():
            ...     print(f"Domain: {domain}")
            ...     for service_name in domain_services.keys():
            ...         print(f"  - {service_name}")
        """
        url = f"{self.base_url}/api/services"

        try:
            async with self.session.get(url) as response:
                # Check for HTTP errors
                await self._handle_response_errors(response)

                # Parse JSON response and return services data
                return await response.json()

        except HAAPIError:
            # Re-raise HAAPIError as-is
            raise
        except Exception as e:
            # Translate network errors to HAAPIError
            raise self._handle_network_error(e, url)

    async def check_config(self) -> Dict[str, Any]:
        """Validate Home Assistant configuration without restarting.

        Makes a POST request to /api/config/core/check_config to validate
        the current configuration and return any errors.

        Returns:
            Dict with validation results (result: 'valid' or 'invalid', errors: error messages if any)

        Raises:
            HAAPIError: If API errors occur or config checking is unavailable

        Example:
            >>> result = await client.check_config()
            >>> if result['result'] == 'valid':
            ...     print("Configuration is valid!")
            >>> else:
            ...     print(f"Configuration errors: {result['errors']}")
        """
        url = f"{self.base_url}/api/config/core/check_config"

        try:
            async with self.session.post(url) as response:
                # Check for HTTP errors
                await self._handle_response_errors(response)

                # Parse JSON response and return validation results
                return await response.json()

        except HAAPIError:
            # Re-raise HAAPIError as-is
            raise
        except Exception as e:
            # Translate network errors to HAAPIError
            raise self._handle_network_error(e, url)

    async def get_error_log(self) -> str:
        """Retrieve all errors logged during the current Home Assistant session.

        Makes a GET request to /api/error_log to retrieve error log entries
        as plain text.

        Returns:
            Error log content as plain text string with timestamps and error messages

        Raises:
            HAAPIError: If API errors occur

        Example:
            >>> error_log = await client.get_error_log()
            >>> print(error_log)
            15-12-20 11:02:50 homeassistant.components.recorder: Found unfinished sessions
            15-12-20 11:03:03 netdisco.ssdp: Error fetching description...
        """
        url = f"{self.base_url}/api/error_log"

        try:
            async with self.session.get(url) as response:
                # Check for HTTP errors
                await self._handle_response_errors(response)

                # Return error log as plain text
                return await response.text()

        except HAAPIError:
            # Re-raise HAAPIError as-is
            raise
        except Exception as e:
            # Translate network errors to HAAPIError
            raise self._handle_network_error(e, url)

    async def get_logbook(
        self,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        entity_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get logbook entries showing entity state changes and events.

        Makes a GET request to /api/logbook to retrieve logbook entries
        with optional filtering by time period and entity.

        Args:
            start_time: Start time in ISO 8601 format (e.g., '2024-01-15T10:00:00+00:00').
                       Defaults to 1 day before the request time.
            end_time: End time in ISO 8601 format. Defaults to now.
            entity_id: Optional entity ID to filter logbook entries (e.g., 'light.living_room')

        Returns:
            List of logbook entry dicts with when, name, message, domain, entity_id, context_user_id

        Raises:
            HAAPIError: If API errors occur

        Example:
            >>> # Get last 24 hours of logbook entries
            >>> entries = await client.get_logbook()
            >>> for entry in entries:
            ...     print(f"{entry['when']}: {entry['name']} {entry['message']}")

            >>> # Get logbook for specific entity and time range
            >>> entries = await client.get_logbook(
            ...     start_time='2024-01-15T00:00:00+00:00',
            ...     end_time='2024-01-16T00:00:00+00:00',
            ...     entity_id='alarm_control_panel.area_001'
            ... )
        """
        # Construct URL with optional start_time
        if start_time:
            url = f"{self.base_url}/api/logbook/{start_time}"
        else:
            url = f"{self.base_url}/api/logbook"

        # Build query parameters
        params = {}
        if end_time:
            params['end_time'] = end_time
        if entity_id:
            params['entity'] = entity_id

        try:
            async with self.session.get(url, params=params) as response:
                # Check for HTTP errors
                await self._handle_response_errors(response)

                # Parse JSON response and return logbook entries
                return await response.json()

        except HAAPIError:
            # Re-raise HAAPIError as-is
            raise
        except Exception as e:
            # Translate network errors to HAAPIError
            raise self._handle_network_error(e, url)



class HAAPIConnection:
    """API-based connection to Home Assistant instance."""
    
    def __init__(self, instance_id: str, base_url: str, access_token: str):
        self.instance_id = instance_id
        self.base_url = base_url.rstrip('/')
        self.access_token = access_token
        self.is_connected = False
        self.session: Optional[aiohttp.ClientSession] = None
        self.headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
    
    async def connect(self) -> None:
        """Connect to HA instance via API."""
        try:
            self.session = aiohttp.ClientSession()
            
            # Test API connectivity
            async with self.session.get(
                f"{self.base_url}/api/",
                headers=self.headers
            ) as response:
                if response.status == 200:
                    api_info = await response.json()
                    self.is_connected = True
                    print(f"Connected to HA API - Version: {api_info.get('version', 'unknown')}")
                else:
                    raise ConnectionError(
                        f"API connection failed: HTTP {response.status}",
                        "API_CONNECTION_FAILED",
                        self.instance_id,
                        True
                    )
                    
        except aiohttp.ClientError as e:
            raise ConnectionError(
                f"Failed to connect to HA API at {self.base_url}: {e}",
                "CONNECTION_FAILED",
                self.instance_id,
                True
            )
    
    async def disconnect(self) -> None:
        """Disconnect from HA instance."""
        if self.session:
            await self.session.close()
            self.session = None
        self.is_connected = False
    
    async def list_files(self, directory: str = "") -> List[str]:
        """List configuration files using File Editor API or custom endpoints."""
        self._ensure_connected()
        
        try:
            # Try to get configuration files through various API methods
            config_files = []
            
            # Method 1: Try File Editor add-on API (if available)
            config_files.extend(await self._list_files_via_file_editor(directory))
            
            # Method 2: Try custom component endpoints
            if not config_files:
                config_files.extend(await self._list_files_via_custom_component(directory))
            
            # Method 3: Fallback to known configuration structure
            if not config_files:
                config_files.extend(await self._list_files_via_known_structure(directory))
            
            return config_files
            
        except Exception as e:
            raise ConnectionError(
                f"Failed to list files in {directory}: {e}",
                "FILE_LIST_FAILED",
                self.instance_id,
                True
            )
    
    async def _list_files_via_file_editor(self, directory: str) -> List[str]:
        """Try to list files via File Editor add-on API."""
        try:
            # File Editor add-on typically provides endpoints like:
            # /api/hassio/addons/core_configurator/info
            # or custom endpoints for file listing
            
            # Check if File Editor services are available
            async with self.session.get(
                f"{self.base_url}/api/services",
                headers=self.headers
            ) as response:
                if response.status == 200:
                    services = await response.json()
                    
                    # Look for file editor related services
                    file_services = []
                    for domain, domain_services in services.items():
                        for service_name in domain_services.keys():
                            if any(keyword in service_name.lower() for keyword in ['file', 'config', 'edit']):
                                file_services.append(f"{domain}.{service_name}")
                    
                    # If file services exist, we can potentially use them
                    # This would require specific File Editor add-on integration
                    return []  # Placeholder - would implement specific add-on API calls
                    
        except Exception:
            pass
        
        return []
    
    async def _list_files_via_custom_component(self, directory: str) -> List[str]:
        """Try to list files via custom component endpoints."""
        try:
            # Custom components might provide endpoints like:
            # /api/config_manager/files
            # This would require a custom HACS component
            
            async with self.session.get(
                f"{self.base_url}/api/config_manager/files",
                headers=self.headers,
                params={"directory": directory}
            ) as response:
                if response.status == 200:
                    files_data = await response.json()
                    return files_data.get('files', [])
                    
        except Exception:
            pass
        
        return []
    
    async def _list_files_via_known_structure(self, directory: str) -> List[str]:
        """Fallback: Try to access known configuration files."""
        known_files = [
            "configuration.yaml",
            "automations.yaml", 
            "scripts.yaml",
            "groups.yaml",
            "scenes.yaml"
        ]
        
        # For packages directory, we'd need to use other API methods
        # to discover what's available
        if directory == "packages":
            # Could potentially use template API to check file existence
            # or other creative API-based methods
            pass
        
        available_files = []
        for filename in known_files:
            if await self._file_exists(filename):
                available_files.append(filename)
        
        return available_files
    
    async def _file_exists(self, filename: str) -> bool:
        """Check if a file exists using API methods."""
        try:
            # Try to read the file - if it succeeds, it exists
            await self.read_file(filename)
            return True
        except:
            return False
    
    async def read_file(self, file_path: str) -> str:
        """Read file content using File Editor API or custom endpoints."""
        self._ensure_connected()
        
        try:
            # Method 1: Try File Editor add-on API
            content = await self._read_file_via_file_editor(file_path)
            if content is not None:
                return content
            
            # Method 2: Try custom component
            content = await self._read_file_via_custom_component(file_path)
            if content is not None:
                return content
            
            # Method 3: For specific files, try alternative API methods
            content = await self._read_file_via_alternative_apis(file_path)
            if content is not None:
                return content
            
            raise ConnectionError(
                f"No available method to read file {file_path}",
                "FILE_READ_NO_METHOD",
                self.instance_id,
                False
            )
            
        except ConnectionError:
            raise
        except Exception as e:
            raise ConnectionError(
                f"Failed to read file {file_path}: {e}",
                "FILE_READ_FAILED",
                self.instance_id,
                True
            )
    
    async def _read_file_via_file_editor(self, file_path: str) -> Optional[str]:
        """Try to read file via File Editor add-on API."""
        try:
            # File Editor add-on might provide endpoints like:
            # POST /api/hassio/addons/core_configurator/options
            # with file reading capabilities
            
            # This would require specific File Editor add-on integration
            # Placeholder for now
            return None
            
        except Exception:
            return None
    
    async def _read_file_via_custom_component(self, file_path: str) -> Optional[str]:
        """Try to read file via custom component."""
        try:
            async with self.session.get(
                f"{self.base_url}/api/config_manager/file",
                headers=self.headers,
                params={"path": file_path}
            ) as response:
                if response.status == 200:
                    file_data = await response.json()
                    return file_data.get('content', '')
                    
        except Exception:
            pass
        
        return None
    
    async def _read_file_via_alternative_apis(self, file_path: str) -> Optional[str]:
        """Try to read specific files via alternative HA APIs."""
        try:
            # For automations.yaml, we can use the automation API
            if file_path == "automations.yaml":
                return await self._read_automations_via_api()
            
            # For scripts.yaml, we can use the script API  
            elif file_path == "scripts.yaml":
                return await self._read_scripts_via_api()
            
            # For configuration.yaml, we can reconstruct from various APIs
            elif file_path == "configuration.yaml":
                return await self._read_config_via_api()
                
        except Exception:
            pass
        
        return None
    
    async def _read_automations_via_api(self) -> str:
        """Read automations using HA automation API."""
        async with self.session.get(
            f"{self.base_url}/api/config/automation/config",
            headers=self.headers
        ) as response:
            if response.status == 200:
                automations = await response.json()
                # Convert back to YAML format
                import yaml
                return yaml.dump(automations, default_flow_style=False)
            else:
                raise Exception(f"Automation API failed: HTTP {response.status}")
    
    async def _read_scripts_via_api(self) -> str:
        """Read scripts using HA script API."""
        async with self.session.get(
            f"{self.base_url}/api/config/script/config", 
            headers=self.headers
        ) as response:
            if response.status == 200:
                scripts = await response.json()
                # Convert back to YAML format
                import yaml
                return yaml.dump(scripts, default_flow_style=False)
            else:
                raise Exception(f"Script API failed: HTTP {response.status}")
    
    async def _read_config_via_api(self) -> str:
        """Reconstruct configuration.yaml from various HA APIs."""
        # This is complex - would need to gather info from multiple APIs
        # and reconstruct the configuration structure
        
        # Get basic HA info
        async with self.session.get(
            f"{self.base_url}/api/config",
            headers=self.headers
        ) as response:
            if response.status == 200:
                config_info = await response.json()
                
                # Build basic configuration structure
                config_yaml = f"""
homeassistant:
  name: {config_info.get('location_name', 'Home')}
  latitude: {config_info.get('latitude', 0)}
  longitude: {config_info.get('longitude', 0)}
  unit_system: {config_info.get('unit_system', {}).get('name', 'metric')}
  time_zone: {config_info.get('time_zone', 'UTC')}

# Configuration managed via HA APIs
# This is a reconstructed view - actual file may differ
"""
                return config_yaml.strip()
            else:
                raise Exception(f"Config API failed: HTTP {response.status}")
    
    async def write_file(self, file_path: str, content: str) -> None:
        """Write file content using File Editor API or custom endpoints."""
        self._ensure_connected()
        
        try:
            # Method 1: Try File Editor add-on API
            if await self._write_file_via_file_editor(file_path, content):
                return
            
            # Method 2: Try custom component
            if await self._write_file_via_custom_component(file_path, content):
                return
            
            # Method 3: For specific files, try alternative API methods
            if await self._write_file_via_alternative_apis(file_path, content):
                return
            
            raise ConnectionError(
                f"No available method to write file {file_path}",
                "FILE_WRITE_NO_METHOD",
                self.instance_id,
                False
            )
            
        except ConnectionError:
            raise
        except Exception as e:
            raise ConnectionError(
                f"Failed to write file {file_path}: {e}",
                "FILE_WRITE_FAILED",
                self.instance_id,
                False
            )
    
    async def _write_file_via_file_editor(self, file_path: str, content: str) -> bool:
        """Try to write file via File Editor add-on API."""
        try:
            # File Editor add-on integration would go here
            # This requires specific add-on API calls
            return False
            
        except Exception:
            return False
    
    async def _write_file_via_custom_component(self, file_path: str, content: str) -> bool:
        """Try to write file via custom component."""
        try:
            async with self.session.post(
                f"{self.base_url}/api/config_manager/file",
                headers=self.headers,
                json={"path": file_path, "content": content}
            ) as response:
                return response.status == 200
                
        except Exception:
            return False
    
    async def _write_file_via_alternative_apis(self, file_path: str, content: str) -> bool:
        """Try to write specific files via alternative HA APIs."""
        try:
            # For automations.yaml, use automation API
            if file_path == "automations.yaml":
                return await self._write_automations_via_api(content)
            
            # For scripts.yaml, use script API
            elif file_path == "scripts.yaml":
                return await self._write_scripts_via_api(content)
                
        except Exception:
            pass
        
        return False
    
    async def _write_automations_via_api(self, content: str) -> bool:
        """Write automations using HA automation API."""
        try:
            import yaml
            automations = yaml.safe_load(content)
            
            # This would require updating each automation individually
            # via the automation config API
            # Complex implementation needed here
            
            return False  # Placeholder
            
        except Exception:
            return False
    
    async def _write_scripts_via_api(self, content: str) -> bool:
        """Write scripts using HA script API."""
        try:
            import yaml
            scripts = yaml.safe_load(content)
            
            # This would require updating each script individually
            # via the script config API
            # Complex implementation needed here
            
            return False  # Placeholder
            
        except Exception:
            return False
    
    async def ping(self) -> bool:
        """Check if API connection is healthy."""
        if not self.session:
            return False
        
        try:
            async with self.session.get(
                f"{self.base_url}/api/",
                headers=self.headers
            ) as response:
                return response.status == 200
                
        except Exception:
            return False
    
    def _ensure_connected(self) -> None:
        """Ensure API connection is established."""
        if not self.is_connected or not self.session:
            raise ConnectionError(
                "API connection not established. Call connect() first.",
                "NOT_CONNECTED",
                self.instance_id,
                True
            )