"""
Integration tests for complete Large File workflow.

Tests the end-to-end workflow:
1. User request → read_config_file
2. Detect truncation from metadata
3. Request subsequent chunks
4. Assemble complete file
5. Verify completeness with hash

Requirements: 2.9, 2.10, 2.11, 2.12, 2.13
"""

import pytest
import hashlib
from unittest.mock import Mock


@pytest.fixture
def large_file_content():
    """Generate large file content (>100KB)."""
    # Create content that's approximately 150KB
    base_content = """
automation:
  - alias: "Test Automation {}"
    trigger:
      - platform: state
        entity_id: sensor.test_{}
    action:
      - service: light.turn_on
        target:
          entity_id: light.test_{}
"""
    
    # Repeat to create large file
    content = ""
    for i in range(1000):  # Creates ~150KB file
        content += base_content.format(i, i, i)
    
    return content


@pytest.fixture
def mock_ha_api_chunked():
    """Mock Home Assistant API with chunking support."""
    api = Mock()
    
    # Store full content for chunking simulation
    full_content = None
    
    def setup_content(content):
        nonlocal full_content
        full_content = content
    
    async def read_with_chunking(path, offset=0, limit=None):
        """Simulate chunked reading."""
        if full_content is None:
            raise ValueError("Content not set up")
        
        total_size = len(full_content)
        
        if limit is None:
            # Return everything from offset
            chunk = full_content[offset:]
            returned_size = len(chunk)
        else:
            # Return limited chunk
            chunk = full_content[offset:offset + limit]
            returned_size = len(chunk)
        
        has_more = (offset + returned_size) < total_size
        truncated = returned_size < (total_size - offset)
        
        return {
            "content": chunk,
            "metadata": {
                "total_size": total_size,
                "returned_size": returned_size,
                "truncated": truncated,
                "offset": offset,
                "has_more": has_more,
                "compressed": False,
                "content_hash": hashlib.sha256(full_content.encode()).hexdigest()
            }
        }
    
    api.read_config_file = read_with_chunking
    api.setup_content = setup_content
    
    return api


class TestLargeFileWorkflow:
    """Test complete large file workflow with chunking."""
    
    @pytest.mark.asyncio
    async def test_complete_large_file_workflow(self, mock_ha_api_chunked, large_file_content):
        """
        Test complete large file workflow with automatic chunking.
        
        Workflow steps:
        1. User request: "Download /config/packages/emhass.yaml"
        2. read_config_file returns first chunk with truncation metadata
        3. Detect truncation from metadata
        4. Request subsequent chunks automatically
        5. Assemble complete file
        6. Verify completeness with hash
        """
        # Setup
        mock_ha_api_chunked.setup_content(large_file_content)
        filename = "packages/emhass.yaml"
        chunk_size = 100000  # 100KB chunks
        
        # Step 1: Initial request
        response = await mock_ha_api_chunked.read_config_file(filename, offset=0, limit=chunk_size)
        
        # Step 2: Check metadata
        metadata = response["metadata"]
        assert metadata["total_size"] > chunk_size, "File should be larger than chunk size"
        assert metadata["truncated"], "First response should be truncated"
        assert metadata["has_more"], "Should have more chunks"
        
        # Step 3: Detect truncation
        is_truncated = metadata["truncated"]
        assert is_truncated, "Should detect truncation"
        
        # Step 4: Request subsequent chunks
        chunks = [response["content"]]
        offset = metadata["returned_size"]
        
        while metadata["has_more"]:
            response = await mock_ha_api_chunked.read_config_file(
                filename,
                offset=offset,
                limit=chunk_size
            )
            chunks.append(response["content"])
            metadata = response["metadata"]
            offset += metadata["returned_size"]
        
        # Step 5: Assemble complete file
        complete_content = "".join(chunks)
        
        # Step 6: Verify completeness
        assert len(complete_content) == len(large_file_content)
        assert complete_content == large_file_content
        
        # Verify hash
        calculated_hash = hashlib.sha256(complete_content.encode()).hexdigest()
        expected_hash = metadata["content_hash"]
        assert calculated_hash == expected_hash
    
    @pytest.mark.asyncio
    async def test_truncation_detection(self, mock_ha_api_chunked, large_file_content):
        """
        Test that truncation is detected from response metadata.
        """
        mock_ha_api_chunked.setup_content(large_file_content)
        
        # Request with limit smaller than file size
        response = await mock_ha_api_chunked.read_config_file(
            "large_file.yaml",
            offset=0,
            limit=50000
        )
        
        metadata = response["metadata"]
        
        # Verify truncation indicators
        assert metadata["truncated"], "Should be truncated"
        assert metadata["has_more"], "Should have more data"
        assert metadata["returned_size"] < metadata["total_size"]
        assert metadata["offset"] == 0
    
    @pytest.mark.asyncio
    async def test_chunk_assembly(self, mock_ha_api_chunked, large_file_content):
        """
        Test that chunks are assembled correctly.
        """
        mock_ha_api_chunked.setup_content(large_file_content)
        chunk_size = 40000
        
        # Collect all chunks
        chunks = []
        offset = 0
        has_more = True
        
        while has_more:
            response = await mock_ha_api_chunked.read_config_file(
                "test.yaml",
                offset=offset,
                limit=chunk_size
            )
            
            chunks.append(response["content"])
            metadata = response["metadata"]
            offset += metadata["returned_size"]
            has_more = metadata["has_more"]
        
        # Assemble
        assembled = "".join(chunks)
        
        # Verify
        assert len(assembled) == len(large_file_content)
        assert assembled == large_file_content
        assert len(chunks) > 1, "Should have multiple chunks"
    
    @pytest.mark.asyncio
    async def test_hash_verification(self, mock_ha_api_chunked, large_file_content):
        """
        Test that final content hash matches expected hash.
        """
        mock_ha_api_chunked.setup_content(large_file_content)
        
        # Get first chunk to get expected hash
        response = await mock_ha_api_chunked.read_config_file(
            "test.yaml",
            offset=0,
            limit=50000
        )
        expected_hash = response["metadata"]["content_hash"]
        
        # Retrieve all chunks
        chunks = []
        offset = 0
        has_more = True
        
        while has_more:
            response = await mock_ha_api_chunked.read_config_file(
                "test.yaml",
                offset=offset,
                limit=50000
            )
            chunks.append(response["content"])
            offset += response["metadata"]["returned_size"]
            has_more = response["metadata"]["has_more"]
        
        # Calculate hash of assembled content
        assembled = "".join(chunks)
        calculated_hash = hashlib.sha256(assembled.encode()).hexdigest()
        
        # Verify
        assert calculated_hash == expected_hash
    
    @pytest.mark.asyncio
    async def test_small_file_no_chunking(self, mock_ha_api_chunked):
        """
        Test that small files are returned in single response without chunking.
        """
        small_content = "homeassistant:\n  name: Test\n"
        mock_ha_api_chunked.setup_content(small_content)
        
        response = await mock_ha_api_chunked.read_config_file(
            "small.yaml",
            offset=0,
            limit=100000
        )
        
        metadata = response["metadata"]
        
        # Verify no chunking needed
        assert not metadata["truncated"]
        assert not metadata["has_more"]
        assert metadata["returned_size"] == metadata["total_size"]
        assert response["content"] == small_content
    
    @pytest.mark.asyncio
    async def test_chunk_count_calculation(self, mock_ha_api_chunked, large_file_content):
        """
        Test that correct number of chunks are requested.
        """
        mock_ha_api_chunked.setup_content(large_file_content)
        chunk_size = 50000
        
        # Calculate expected chunks
        total_size = len(large_file_content)
        expected_chunks = (total_size + chunk_size - 1) // chunk_size
        
        # Retrieve all chunks
        chunk_count = 0
        offset = 0
        has_more = True
        
        while has_more:
            response = await mock_ha_api_chunked.read_config_file(
                "test.yaml",
                offset=offset,
                limit=chunk_size
            )
            chunk_count += 1
            offset += response["metadata"]["returned_size"]
            has_more = response["metadata"]["has_more"]
        
        # Verify chunk count
        assert chunk_count == expected_chunks
    
    @pytest.mark.asyncio
    async def test_real_world_emhass_file(self, mock_ha_api_chunked):
        """
        Test with realistic emhass.yaml file structure.
        
        Real-world test case: /config/packages/emhass.yaml
        """
        # Simulate realistic emhass.yaml content (large configuration)
        emhass_content = """
# EMHASS Configuration Package
homeassistant:
  customize:
"""
        
        # Add many sensor configurations to make it large
        for i in range(500):
            emhass_content += f"""
    sensor.emhass_power_{i}:
      friendly_name: "EMHASS Power Sensor {i}"
      unit_of_measurement: "W"
      device_class: power
"""
        
        emhass_content += """
sensor:
  - platform: rest
    name: emhass_forecast
    resource: http://localhost:5000/action/forecast
"""
        
        # Add more content to exceed 100KB
        for i in range(200):
            emhass_content += f"""
  - platform: template
    sensors:
      emhass_sensor_{i}:
        friendly_name: "EMHASS Sensor {i}"
        value_template: "{{{{ states('sensor.power') }}}}"
"""
        
        mock_ha_api_chunked.setup_content(emhass_content)
        
        # Retrieve with chunking
        chunks = []
        offset = 0
        has_more = True
        chunk_size = 100000
        
        while has_more:
            response = await mock_ha_api_chunked.read_config_file(
                "packages/emhass.yaml",
                offset=offset,
                limit=chunk_size
            )
            chunks.append(response["content"])
            offset += response["metadata"]["returned_size"]
            has_more = response["metadata"]["has_more"]
        
        # Verify complete retrieval
        complete = "".join(chunks)
        assert len(complete) == len(emhass_content)
        assert complete == emhass_content
        assert "EMHASS Configuration Package" in complete
        assert "emhass_forecast" in complete
    
    @pytest.mark.asyncio
    async def test_metadata_consistency_across_chunks(self, mock_ha_api_chunked, large_file_content):
        """
        Test that metadata remains consistent across all chunks.
        """
        mock_ha_api_chunked.setup_content(large_file_content)
        
        # Collect metadata from all chunks
        metadata_list = []
        offset = 0
        has_more = True
        
        while has_more:
            response = await mock_ha_api_chunked.read_config_file(
                "test.yaml",
                offset=offset,
                limit=50000
            )
            metadata_list.append(response["metadata"])
            offset += response["metadata"]["returned_size"]
            has_more = response["metadata"]["has_more"]
        
        # Verify consistency
        first_metadata = metadata_list[0]
        for metadata in metadata_list:
            assert metadata["total_size"] == first_metadata["total_size"]
            assert metadata["content_hash"] == first_metadata["content_hash"]
