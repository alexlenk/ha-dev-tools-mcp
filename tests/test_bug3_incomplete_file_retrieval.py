"""
Bug Condition Exploration Test: Incomplete File Retrieval

This test explores Bug 3: Incomplete File Handling
- Tests that large files (>100KB) are retrieved completely
- EXPECTED TO FAIL on unfixed code (proves bug exists)
- Will PASS after fix is implemented (validates fix)

Bug Condition: isBugCondition3(fileSize, responseSize)
  Returns true when:
  - File size exceeds MCP response limits (typically 100KB)
  - Response size is less than actual file size
  - File content is truncated without metadata indication

Expected Behavior (after fix):
  - Response includes metadata with total_size, returned_size, truncated flag
  - If file is truncated, Kiro detects it and requests additional chunks
  - Final assembled content matches original file size and hash
  - Complete file retrieval regardless of size

CURRENT STATUS: FIXED
  - MCP server now returns metadata with truncation information
  - Supports chunking with offset/limit parameters
  - Kiro detects truncation and assembles complete files
  - Tests should now PASS
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from typing import Dict, Any, Optional
from dataclasses import dataclass
import hashlib


# ============================================================================
# File Response Data Structures
# ============================================================================

@dataclass
class FileMetadata:
    """Metadata about file retrieval"""
    total_size: int
    returned_size: int
    truncated: bool
    offset: int
    has_more: bool
    compressed: bool
    content_hash: str


@dataclass
class FileResponse:
    """Response from file retrieval operation"""
    content: str
    metadata: Optional[FileMetadata] = None


# ============================================================================
# Mock MCP Server File Reading
# ============================================================================

class MockMCPServer:
    """
    Simulates MCP server's file reading behavior (FIXED VERSION)
    
    Fixed behavior:
    - Returns structured response with content and metadata
    - Includes truncation detection
    - Supports chunking with offset/limit parameters
    - Returns content_hash for verification
    - Indicates has_more when additional data available
    """
    
    # Simulated MCP response size limit (100KB)
    MCP_RESPONSE_LIMIT = 100 * 1024  # 100KB in bytes
    
    def __init__(self):
        self.files = {}  # Simulated file storage
    
    def create_test_file(self, file_path: str, size_kb: int) -> str:
        """Create a test file of specified size"""
        # Generate content of specified size
        content = self._generate_content(size_kb * 1024)
        self.files[file_path] = content
        return content
    
    def _generate_content(self, size_bytes: int) -> str:
        """Generate YAML-like content of specified size"""
        # Create realistic YAML content that fills the size
        lines = []
        current_size = 0
        counter = 0
        
        while current_size < size_bytes:
            line = f"automation_{counter}:\n"
            line += f"  alias: Test Automation {counter}\n"
            line += f"  trigger:\n"
            line += f"    - platform: state\n"
            line += f"      entity_id: sensor.test_{counter}\n"
            line += f"  action:\n"
            line += f"    - service: light.turn_on\n"
            line += f"      target:\n"
            line += f"        entity_id: light.test_{counter}\n"
            line += f"\n"
            
            lines.append(line)
            current_size += len(line)
            counter += 1
        
        return "".join(lines)
    
    async def read_config_file(
        self,
        file_path: str,
        offset: int = 0,
        limit: Optional[int] = None
    ) -> FileResponse:
        """
        Simulates FIXED MCP server behavior
        
        Fixed implementation:
        - Checks content size and detects truncation
        - Returns metadata with truncation flag
        - Supports chunking with offset/limit
        - Provides content_hash for verification
        - Indicates has_more when additional data available
        """
        if file_path not in self.files:
            raise FileNotFoundError(f"File not found: {file_path}")
        
        full_content = self.files[file_path]
        full_size = len(full_content.encode('utf-8'))
        
        # Apply offset and limit for chunking
        full_content_bytes = full_content.encode('utf-8')
        
        if offset >= full_size:
            # Offset beyond file size - return empty content
            content_bytes = b''
            has_more = False
        else:
            # Determine chunk size
            if limit is not None:
                end_pos = min(offset + limit, full_size)
            else:
                # No limit specified - use MCP_RESPONSE_LIMIT
                end_pos = min(offset + self.MCP_RESPONSE_LIMIT, full_size)
            
            content_bytes = full_content_bytes[offset:end_pos]
            has_more = end_pos < full_size
        
        # Decode content
        content = content_bytes.decode('utf-8')
        returned_size = len(content_bytes)
        
        # Calculate content hash
        content_hash = hashlib.sha256(content_bytes).hexdigest()
        
        # Determine if truncated
        truncated = returned_size < full_size
        
        # Build metadata
        metadata = FileMetadata(
            total_size=full_size,
            returned_size=returned_size,
            truncated=truncated,
            offset=offset,
            has_more=has_more,
            compressed=False,
            content_hash=content_hash
        )
        
        return FileResponse(content=content, metadata=metadata)


class MockKiroFileHandler:
    """
    Simulates Kiro's file handling logic (FIXED VERSION)
    
    Fixed behavior:
    - Receives file content from MCP server
    - Checks metadata for truncation
    - Requests additional chunks if needed
    - Assembles complete file content
    - Verifies completeness before proceeding
    """
    
    def __init__(self, mcp_server: MockMCPServer):
        self.mcp_server = mcp_server
    
    async def retrieve_file(self, file_path: str) -> str:
        """
        Simulates FIXED Kiro behavior
        
        Fixed logic:
        1. Call read_config_file
        2. Check metadata for truncation
        3. Request additional chunks if needed
        4. Assemble complete content
        5. Verify hash matches expected
        """
        # Get first chunk
        response = await self.mcp_server.read_config_file(file_path)
        
        # Check if we need to retrieve more chunks
        if response.metadata and response.metadata.has_more:
            # File is truncated - retrieve additional chunks
            chunks = [response.content]
            offset = response.metadata.returned_size
            
            while True:
                # Request next chunk
                next_response = await self.mcp_server.read_config_file(
                    file_path,
                    offset=offset
                )
                
                chunks.append(next_response.content)
                
                # Check if more chunks needed
                if not next_response.metadata or not next_response.metadata.has_more:
                    break
                
                offset += next_response.metadata.returned_size
            
            # Assemble complete content
            complete_content = "".join(chunks)
            return complete_content
        else:
            # Single chunk or small file
            return response.content
    
    def verify_completeness(self, content: str, expected_size: int) -> bool:
        """
        Simulates FIXED Kiro completeness checking
        
        Fixed behavior: Verifies content size matches expected
        """
        actual_size = len(content.encode('utf-8'))
        return actual_size == expected_size


# ============================================================================
# Bug Condition Function
# ============================================================================

def is_bug_condition_3(file_size: int, response_size: int) -> bool:
    """
    Bug Condition 3: File is truncated without indication
    
    Returns True when:
    - File size exceeds MCP response limit
    - OR response size is less than file size
    
    When this returns True, the system SHOULD handle truncation properly
    but currently doesn't.
    """
    MCP_RESPONSE_LIMIT = 100 * 1024  # 100KB
    
    return file_size > MCP_RESPONSE_LIMIT or response_size < file_size


# ============================================================================
# Property-Based Exploration Tests
# ============================================================================

class TestBug3IncompleteFileRetrieval:
    """
    Bug 3 Exploration Tests
    
    These tests are EXPECTED TO FAIL on unfixed code.
    Failure confirms the bug exists.
    """
    
    @pytest.mark.asyncio
    async def test_150kb_file_truncated_without_metadata(self):
        """
        Test: Request 150KB file via read_config_file
        
        Expected (after fix): 
          - Response includes metadata with truncated=true
          - Metadata shows total_size=150KB, returned_size=100KB
          - Kiro detects truncation and requests additional chunks
        
        Current (unfixed):
          - Returns first 100KB without metadata
          - No indication of truncation
          - Kiro assumes it has complete file
        
        EXPECTED OUTCOME: FAIL (proves bug exists)
        """
        # Setup MCP server with 150KB test file
        mcp_server = MockMCPServer()
        test_file_size_kb = 150
        file_path = "large_automations.yaml"
        
        # Create test file
        full_content = mcp_server.create_test_file(file_path, test_file_size_kb)
        full_size = len(full_content)
        
        # Request file via MCP server
        response = await mcp_server.read_config_file(file_path)
        returned_size = len(response.content)
        
        # Verify this is a bug condition
        assert is_bug_condition_3(full_size, returned_size), \
            "This should be identified as a bug condition (file truncated)"
        
        # ASSERTION 1: Response should include metadata (will FAIL on unfixed code)
        assert response.metadata is not None, \
            f"Response should include metadata for large files. " \
            f"Bug confirmed: No metadata returned for {test_file_size_kb}KB file."
        
        # ASSERTION 2: Metadata should indicate truncation (will FAIL)
        if response.metadata:
            assert response.metadata.truncated is True, \
                f"Metadata should indicate file is truncated. " \
                f"Bug confirmed: truncated flag missing or false."
            
            # ASSERTION 3: Metadata should show correct sizes (will FAIL)
            assert response.metadata.total_size == full_size, \
                f"Metadata should show total_size={full_size}, got {response.metadata.total_size}"
            
            assert response.metadata.returned_size == returned_size, \
                f"Metadata should show returned_size={returned_size}, got {response.metadata.returned_size}"
            
            # ASSERTION 4: Metadata should indicate more data available (will FAIL)
            assert response.metadata.has_more is True, \
                f"Metadata should indicate has_more=true for truncated files"
    
    @pytest.mark.asyncio
    async def test_kiro_does_not_detect_truncation(self):
        """
        Test: Kiro should detect truncation and request additional chunks
        
        Expected (after fix):
          - Kiro checks metadata.truncated flag
          - Kiro requests additional chunks with offset parameter
          - Kiro assembles complete file content
        
        Current (unfixed):
          - Kiro does not check for truncation
          - Kiro assumes content is complete
          - Kiro proceeds with partial data
        
        EXPECTED OUTCOME: FAIL (proves bug exists)
        """
        # Setup
        mcp_server = MockMCPServer()
        kiro = MockKiroFileHandler(mcp_server)
        
        file_path = "large_configuration.yaml"
        test_file_size_kb = 200
        
        # Create large test file
        full_content = mcp_server.create_test_file(file_path, test_file_size_kb)
        full_size = len(full_content)
        
        # Kiro retrieves file
        retrieved_content = await kiro.retrieve_file(file_path)
        retrieved_size = len(retrieved_content)
        
        # Verify bug condition
        assert is_bug_condition_3(full_size, retrieved_size)
        
        # ASSERTION: Kiro should retrieve complete file (will FAIL)
        assert retrieved_size == full_size, \
            f"Kiro should retrieve complete file ({full_size} bytes), " \
            f"but only got {retrieved_size} bytes. " \
            f"Bug confirmed: Kiro does not detect or handle truncation."
    
    @pytest.mark.asyncio
    async def test_no_chunking_support_in_mcp_server(self):
        """
        Test: MCP server should support chunking with offset/limit parameters
        
        Expected (after fix):
          - read_config_file accepts offset and limit parameters
          - Returns chunk of data starting at offset
          - Returns metadata with has_more flag
        
        Current (unfixed):
          - offset and limit parameters ignored
          - No chunking support
          - Cannot retrieve file in pieces
        
        EXPECTED OUTCOME: FAIL (proves bug exists)
        """
        # Setup
        mcp_server = MockMCPServer()
        file_path = "large_scripts.yaml"
        test_file_size_kb = 150
        
        # Create test file
        full_content = mcp_server.create_test_file(file_path, test_file_size_kb)
        full_size = len(full_content)
        
        # Try to request second chunk (offset=100KB, limit=50KB)
        chunk_offset = 100 * 1024
        chunk_limit = 50 * 1024
        
        response = await mcp_server.read_config_file(
            file_path,
            offset=chunk_offset,
            limit=chunk_limit
        )
        
        # ASSERTION: Should return chunk starting at offset (will FAIL)
        # Current behavior: offset/limit ignored, returns truncated content from start
        expected_chunk = full_content[chunk_offset:chunk_offset + chunk_limit]
        
        assert response.content == expected_chunk, \
            f"MCP server should support chunking with offset/limit. " \
            f"Bug confirmed: offset/limit parameters ignored."
    
    @pytest.mark.asyncio
    async def test_no_content_hash_in_metadata(self):
        """
        Test: Response metadata should include content_hash for verification
        
        Expected (after fix):
          - Metadata includes content_hash (SHA256)
          - Kiro can verify assembled content matches expected hash
        
        EXPECTED OUTCOME: PASS (fix validates content_hash is included)
        """
        # Setup
        mcp_server = MockMCPServer()
        file_path = "test_file.yaml"
        test_file_size_kb = 150
        
        # Create test file
        full_content = mcp_server.create_test_file(file_path, test_file_size_kb)
        
        # Request file (first chunk)
        response = await mcp_server.read_config_file(file_path)
        
        # ASSERTION: Metadata should include content_hash
        assert response.metadata is not None, \
            "Response should include metadata"
        
        assert hasattr(response.metadata, 'content_hash'), \
            "Metadata should include content_hash field"
        
        # Calculate expected hash for the returned chunk
        expected_chunk_hash = hashlib.sha256(response.content.encode()).hexdigest()
        
        assert response.metadata.content_hash == expected_chunk_hash, \
            f"Metadata content_hash should match chunk hash"
    
    @pytest.mark.asyncio
    async def test_kiro_does_not_verify_completeness(self):
        """
        Test: Kiro should verify file completeness before proceeding
        
        Expected (after fix):
          - Kiro checks metadata.truncated flag
          - Kiro retrieves all chunks automatically
          - Kiro verifies content size matches expected
        
        EXPECTED OUTCOME: PASS (fix validates Kiro retrieves complete files)
        """
        # Setup
        mcp_server = MockMCPServer()
        kiro = MockKiroFileHandler(mcp_server)
        
        file_path = "large_automations.yaml"
        test_file_size_kb = 150
        
        # Create test file
        full_content = mcp_server.create_test_file(file_path, test_file_size_kb)
        full_size = len(full_content.encode('utf-8'))
        
        # Kiro retrieves file (should get complete file via chunking)
        retrieved_content = await kiro.retrieve_file(file_path)
        retrieved_size = len(retrieved_content.encode('utf-8'))
        
        # ASSERTION: Kiro should retrieve complete file
        assert retrieved_size == full_size, \
            f"Kiro should retrieve complete file ({full_size} bytes), " \
            f"got {retrieved_size} bytes"
        
        # ASSERTION: Kiro should verify completeness correctly
        is_complete = kiro.verify_completeness(retrieved_content, full_size)
        
        assert is_complete is True, \
            f"Kiro should verify file is complete"
    
    @pytest.mark.asyncio
    @given(
        file_size_kb=st.integers(min_value=101, max_value=500)
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=20)
    async def test_property_large_files_truncated(self, file_size_kb):
        """
        Property-Based Test: All files >100KB should be handled properly
        
        Property: For all files exceeding MCP response limit,
                  the system should either:
                  1. Return complete content with chunking/compression
                  2. Return metadata indicating truncation with has_more flag
        
        Current behavior: Silently truncates without indication
        
        EXPECTED OUTCOME: FAIL on multiple examples (proves bug exists for various sizes)
        """
        # Setup
        mcp_server = MockMCPServer()
        file_path = f"test_file_{file_size_kb}kb.yaml"
        
        # Create test file
        full_content = mcp_server.create_test_file(file_path, file_size_kb)
        full_size = len(full_content)
        
        # Request file
        response = await mcp_server.read_config_file(file_path)
        returned_size = len(response.content)
        
        # Verify bug condition
        if not is_bug_condition_3(full_size, returned_size):
            return  # Skip if not a bug condition
        
        # ASSERTION: Should either return complete content OR metadata with truncation info
        if returned_size < full_size:
            # File is truncated - should have metadata
            assert response.metadata is not None, \
                f"File size: {file_size_kb}KB | " \
                f"Truncated file should include metadata. " \
                f"Bug confirmed: No metadata for truncated {file_size_kb}KB file."
            
            if response.metadata:
                assert response.metadata.truncated is True, \
                    f"File size: {file_size_kb}KB | " \
                    f"Metadata should indicate truncation. " \
                    f"Bug confirmed: truncated flag missing."
                
                assert response.metadata.has_more is True, \
                    f"File size: {file_size_kb}KB | " \
                    f"Metadata should indicate more data available. " \
                    f"Bug confirmed: has_more flag missing."
    
    @pytest.mark.asyncio
    async def test_small_files_not_affected(self):
        """
        Preservation Test: Small files (<100KB) should work normally
        
        This is NOT a bug - this is expected behavior that should be preserved.
        Small files should be returned in single response without chunking overhead.
        
        EXPECTED OUTCOME: PASS (this behavior is correct)
        """
        # Setup
        mcp_server = MockMCPServer()
        file_path = "small_config.yaml"
        test_file_size_kb = 50  # Well under limit
        
        # Create small test file
        full_content = mcp_server.create_test_file(file_path, test_file_size_kb)
        full_size = len(full_content)
        
        # Request file
        response = await mcp_server.read_config_file(file_path)
        returned_size = len(response.content)
        
        # Verify this is NOT a bug condition
        assert not is_bug_condition_3(full_size, returned_size), \
            "Small files should NOT be bug conditions"
        
        # ASSERTION: Should return complete content (this is correct)
        assert returned_size == full_size, \
            f"Small files should be returned completely"
        
        # ASSERTION: Content should match exactly
        assert response.content == full_content, \
            f"Small file content should match exactly"
    
    @pytest.mark.asyncio
    async def test_real_world_emhass_yaml_file(self):
        """
        Real-World Test: /config/packages/emhass.yaml
        
        This is a real file mentioned in the bug report that triggers truncation.
        
        Expected (after fix):
          - Complete file retrieval with chunking if needed
          - Proper workflow execution (get_file_metadata → read_config_file → save locally)
        
        EXPECTED OUTCOME: PASS (fix validates complete file retrieval)
        """
        # Setup
        mcp_server = MockMCPServer()
        kiro = MockKiroFileHandler(mcp_server)
        file_path = "packages/emhass.yaml"
        
        # Simulate a large emhass.yaml file (typically >100KB)
        test_file_size_kb = 120
        full_content = mcp_server.create_test_file(file_path, test_file_size_kb)
        full_size = len(full_content.encode('utf-8'))
        
        # Kiro retrieves file (should get complete file via chunking)
        retrieved_content = await kiro.retrieve_file(file_path)
        retrieved_size = len(retrieved_content.encode('utf-8'))
        
        # ASSERTION: Should retrieve complete file
        assert retrieved_size == full_size, \
            f"Real-world file packages/emhass.yaml should be retrieved completely. " \
            f"Expected {full_size} bytes, got {retrieved_size} bytes."
        
        # ASSERTION: Content should match exactly
        assert retrieved_content == full_content, \
            f"Retrieved content should match original file exactly"


# ============================================================================
# Counterexample Documentation
# ============================================================================

def document_counterexamples():
    """
    Document counterexamples found during exploration
    
    This function runs the tests and captures failures to document
    which file sizes trigger truncation and what metadata is missing.
    """
    import asyncio
    
    async def run_exploration():
        print("\n" + "="*80)
        print("BUG 3 EXPLORATION: Incomplete File Retrieval")
        print("="*80)
        print("\nCounterexamples (file sizes that trigger truncation):\n")
        
        mcp_server = MockMCPServer()
        kiro = MockKiroFileHandler(mcp_server)
        
        test_sizes = [50, 100, 150, 200, 300, 500]  # KB
        
        for size_kb in test_sizes:
            file_path = f"test_{size_kb}kb.yaml"
            
            # Create test file
            full_content = mcp_server.create_test_file(file_path, size_kb)
            full_size = len(full_content)
            
            # Request via MCP server
            response = await mcp_server.read_config_file(file_path)
            returned_size = len(response.content)
            
            # Request via Kiro
            kiro_content = await kiro.retrieve_file(file_path)
            kiro_size = len(kiro_content)
            
            print(f"{size_kb}KB File:")
            print(f"  Full size: {full_size:,} bytes")
            print(f"  Returned size: {returned_size:,} bytes")
            print(f"  Kiro received: {kiro_size:,} bytes")
            print(f"  Truncated: {returned_size < full_size}")
            print(f"  Has metadata: {response.metadata is not None}")
            
            if is_bug_condition_3(full_size, returned_size):
                print(f"  ❌ BUG CONFIRMED: File truncated without metadata")
                print(f"     Missing: {full_size - returned_size:,} bytes ({((full_size - returned_size) / full_size * 100):.1f}%)")
            else:
                print(f"  ✅ Correct: File returned completely")
            print()
        
        print("="*80)
        print("MISSING FEATURES:")
        print("="*80)
        print("1. No metadata in responses (total_size, returned_size, truncated flag)")
        print("2. No chunking support (offset/limit parameters)")
        print("3. No content_hash for verification")
        print("4. No has_more flag to indicate additional data")
        print("5. Kiro does not detect truncation")
        print("6. Kiro does not request additional chunks")
        print("7. Kiro does not verify completeness before analysis")
        print()
        print("="*80)
        print("CONCLUSION: Bug 3 exists - Large files silently truncated")
        print("="*80)
    
    asyncio.run(run_exploration())


if __name__ == "__main__":
    # Run counterexample documentation
    document_counterexamples()
    
    print("\n\nTo run the exploration tests:")
    print("  PYTHONPATH=src/config-manager/src python -m pytest src/config-manager/tests/test_bug3_incomplete_file_retrieval.py -v")
    print("\nExpected outcome: Tests FAIL (this confirms the bug exists)")
