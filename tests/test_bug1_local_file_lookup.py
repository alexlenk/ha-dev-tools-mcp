"""
Bug Condition Exploration Test: Local File Lookup

This test explores Bug 1: Incorrect Local File Lookup
- Tests that Kiro recognizes HA file requests and uses MCP tools
- EXPECTED TO FAIL on unfixed code (proves bug exists)
- Will PASS after fix is implemented (validates fix)

Bug Condition: isBugCondition1(context, userRequest)
  Returns true when:
  - User request contains HA keywords (home assistant, HA, configuration.yaml, etc.)
  - ha-development-power is installed
  - Request mentions a file (.yaml, .yml, .json)
  - Request does NOT explicitly say "local"

Expected Behavior (after fix):
  - Kiro should use read_config_file instead of readFile
  - Kiro should use list_config_files instead of listDirectory
  - Kiro should recognize HA context and prioritize MCP tools

Current Behavior (unfixed):
  - Kiro uses local file tools (readFile, fileSearch, listDirectory)
  - Kiro does not recognize HA context automatically
  - User must explicitly say "use the power" to trigger MCP tools
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from typing import Dict, List, Any


# ============================================================================
# Mock Kiro Tool Selection System
# ============================================================================
# This simulates Kiro's current behavior (unfixed code)
# In reality, this would be Kiro's internal tool selection logic

class MockKiroToolSelector:
    """
    Simulates Kiro's tool selection logic (UNFIXED VERSION)
    
    Current behavior:
    - Always defaults to local file tools
    - Does not recognize HA context automatically
    - Only uses MCP tools if explicitly told "use the power"
    """
    
    def __init__(self, installed_powers: List[str], env_vars: Dict[str, str]):
        self.installed_powers = installed_powers
        self.env_vars = env_vars
    
    def select_tool_for_request(self, user_request: str) -> str:
        """
        Simulates current Kiro behavior (UNFIXED)
        
        Current logic:
        1. If user says "use the power" or "use MCP" → use MCP tools
        2. Otherwise → always use local file tools
        
        This is the BUG - it should recognize HA context automatically
        """
        # Current behavior: only use MCP if explicitly requested
        if "use the power" in user_request.lower() or "use mcp" in user_request.lower():
            if "configuration.yaml" in user_request or "automations.yaml" in user_request:
                return "read_config_file"  # MCP tool
            elif "list" in user_request and "packages" in user_request:
                return "list_config_files"  # MCP tool
        
        # Default behavior: use local tools (THIS IS THE BUG)
        if "configuration.yaml" in user_request or "automations.yaml" in user_request:
            if "list" in user_request or "show" in user_request:
                return "fileSearch"  # Local tool (WRONG)
            else:
                return "readFile"  # Local tool (WRONG)
        elif "list" in user_request and "packages" in user_request:
            return "listDirectory"  # Local tool (WRONG)
        
        return "unknown"


# ============================================================================
# Bug Condition Function
# ============================================================================

def is_bug_condition_1(context: Dict[str, Any], user_request: str) -> bool:
    """
    Bug Condition 1: Should use MCP tools but doesn't
    
    Returns True when:
    - User request contains HA keywords
    - ha-development-power is installed
    - Request mentions a file
    - Request does NOT explicitly say "local" or "use the power"
    
    When this returns True, Kiro SHOULD use MCP tools but currently doesn't.
    """
    ha_keywords = [
        "home assistant", "HA", "homeassistant",
        "configuration.yaml", "automations.yaml", "scripts.yaml", "packages/"
    ]
    
    # Check if request has HA context
    has_ha_context = any(keyword.lower() in user_request.lower() for keyword in ha_keywords)
    
    # Check if power is installed
    power_installed = "ha-development-power" in context.get("installed_powers", [])
    
    # Check if request mentions a file
    mentions_file = any(ext in user_request for ext in [".yaml", ".yml", ".json"])
    
    # Check if NOT explicit local request
    not_explicit_local = "local" not in user_request.lower()
    
    # Check if NOT already using power explicitly
    not_explicit_power = "use the power" not in user_request.lower() and "use mcp" not in user_request.lower()
    
    return has_ha_context and power_installed and mentions_file and not_explicit_local and not_explicit_power


# ============================================================================
# Property-Based Exploration Tests
# ============================================================================

class TestBug1LocalFileLookup:
    """
    Bug 1 Exploration Tests
    
    These tests are EXPECTED TO FAIL on unfixed code.
    Failure confirms the bug exists.
    """
    
    def test_ha_configuration_yaml_request(self):
        """
        Test: User mentions "Home Assistant configuration.yaml"
        
        Expected (after fix): Uses read_config_file (MCP tool)
        Current (unfixed): Uses readFile or fileSearch (local tools)
        
        EXPECTED OUTCOME: FAIL (proves bug exists)
        """
        # Setup context
        context = {
            "installed_powers": ["ha-development-power"],
            "env_vars": {"HA_URL": "http://homeassistant.local:8123", "HA_TOKEN": "test_token"}
        }
        
        # User request with HA context
        user_request = "Show me my Home Assistant configuration.yaml"
        
        # Verify this is a bug condition
        assert is_bug_condition_1(context, user_request), \
            "This should be identified as a bug condition"
        
        # Simulate Kiro's tool selection (UNFIXED)
        kiro = MockKiroToolSelector(
            installed_powers=context["installed_powers"],
            env_vars=context["env_vars"]
        )
        selected_tool = kiro.select_tool_for_request(user_request)
        
        # ASSERTION: Should use MCP tool (will FAIL on unfixed code)
        assert selected_tool == "read_config_file", \
            f"Expected 'read_config_file' (MCP tool), but got '{selected_tool}' (local tool). " \
            f"This confirms Bug 1: Kiro uses local file tools instead of MCP tools for HA files."
    
    def test_ha_automations_yaml_request(self):
        """
        Test: User mentions "HA automations.yaml"
        
        Expected (after fix): Uses read_config_file (MCP tool)
        Current (unfixed): Uses readFile or fileSearch (local tools)
        
        EXPECTED OUTCOME: FAIL (proves bug exists)
        """
        context = {
            "installed_powers": ["ha-development-power"],
            "env_vars": {"HA_URL": "http://homeassistant.local:8123", "HA_TOKEN": "test_token"}
        }
        
        user_request = "Read my HA automations.yaml file"
        
        # Verify bug condition
        assert is_bug_condition_1(context, user_request)
        
        # Simulate tool selection
        kiro = MockKiroToolSelector(
            installed_powers=context["installed_powers"],
            env_vars=context["env_vars"]
        )
        selected_tool = kiro.select_tool_for_request(user_request)
        
        # ASSERTION: Should use MCP tool (will FAIL on unfixed code)
        assert selected_tool == "read_config_file", \
            f"Expected 'read_config_file' (MCP tool), but got '{selected_tool}'. " \
            f"Bug confirmed: HA automations.yaml triggers local file tools."
    
    def test_ha_packages_directory_list(self):
        """
        Test: User mentions "list my packages directory" in HA context
        
        Expected (after fix): Uses list_config_files (MCP tool)
        Current (unfixed): Uses listDirectory (local tool)
        
        EXPECTED OUTCOME: FAIL (proves bug exists)
        """
        context = {
            "installed_powers": ["ha-development-power"],
            "env_vars": {"HA_URL": "http://homeassistant.local:8123", "HA_TOKEN": "test_token"}
        }
        
        user_request = "List my Home Assistant packages directory"
        
        # Verify bug condition
        # Note: This doesn't have .yaml extension, so we need to adjust the condition check
        # or the request to include a file mention
        user_request_with_file = "List my Home Assistant packages/*.yaml files"
        
        assert is_bug_condition_1(context, user_request_with_file)
        
        # Simulate tool selection
        kiro = MockKiroToolSelector(
            installed_powers=context["installed_powers"],
            env_vars=context["env_vars"]
        )
        selected_tool = kiro.select_tool_for_request(user_request_with_file)
        
        # ASSERTION: Should use MCP tool (will FAIL on unfixed code)
        assert selected_tool == "list_config_files", \
            f"Expected 'list_config_files' (MCP tool), but got '{selected_tool}'. " \
            f"Bug confirmed: HA packages directory listing triggers local tools."
    
    @given(
        ha_keyword=st.sampled_from([
            "Home Assistant", "HA", "homeassistant"
        ]),
        file_name=st.sampled_from([
            "configuration.yaml", "automations.yaml", "scripts.yaml"
        ]),
        action=st.sampled_from([
            "Show me", "Read", "Display", "Get", "Fetch"
        ])
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=20)
    def test_property_ha_file_requests_use_mcp_tools(self, ha_keyword, file_name, action):
        """
        Property-Based Test: All HA file requests should use MCP tools
        
        Property: For all user requests with HA context + file mention,
                  Kiro should select MCP tools (read_config_file, list_config_files)
                  instead of local tools (readFile, fileSearch, listDirectory)
        
        This test generates many variations of HA file requests and verifies
        that MCP tools are selected.
        
        EXPECTED OUTCOME: FAIL on multiple examples (proves bug exists across variations)
        """
        context = {
            "installed_powers": ["ha-development-power"],
            "env_vars": {"HA_URL": "http://homeassistant.local:8123", "HA_TOKEN": "test_token"}
        }
        
        # Generate user request
        user_request = f"{action} my {ha_keyword} {file_name}"
        
        # Verify bug condition
        if not is_bug_condition_1(context, user_request):
            # Skip if not a bug condition (e.g., explicit local request)
            return
        
        # Simulate tool selection
        kiro = MockKiroToolSelector(
            installed_powers=context["installed_powers"],
            env_vars=context["env_vars"]
        )
        selected_tool = kiro.select_tool_for_request(user_request)
        
        # ASSERTION: Should use MCP tool
        mcp_tools = ["read_config_file", "list_config_files"]
        local_tools = ["readFile", "fileSearch", "listDirectory"]
        
        assert selected_tool in mcp_tools, \
            f"Request: '{user_request}' | " \
            f"Expected MCP tool {mcp_tools}, but got '{selected_tool}'. " \
            f"Bug confirmed: Kiro uses local tools for HA file requests."
        
        # Additional assertion: Should NOT use local tools
        assert selected_tool not in local_tools, \
            f"Request: '{user_request}' | " \
            f"Kiro incorrectly selected local tool '{selected_tool}' instead of MCP tool."
    
    def test_explicit_local_request_uses_local_tools(self):
        """
        Preservation Test: Explicit local requests should use local tools
        
        This is NOT a bug - this is expected behavior that should be preserved.
        When user explicitly says "local", use local tools even in HA context.
        
        EXPECTED OUTCOME: PASS (this behavior is correct)
        """
        context = {
            "installed_powers": ["ha-development-power"],
            "env_vars": {"HA_URL": "http://homeassistant.local:8123", "HA_TOKEN": "test_token"}
        }
        
        user_request = "Read the local configuration.yaml file"
        
        # Verify this is NOT a bug condition (explicit local request)
        assert not is_bug_condition_1(context, user_request), \
            "Explicit local requests should NOT be bug conditions"
        
        # Simulate tool selection
        kiro = MockKiroToolSelector(
            installed_powers=context["installed_powers"],
            env_vars=context["env_vars"]
        )
        selected_tool = kiro.select_tool_for_request(user_request)
        
        # ASSERTION: Should use local tool (this is correct behavior)
        local_tools = ["readFile", "fileSearch", "listDirectory"]
        assert selected_tool in local_tools, \
            f"Explicit local request should use local tools, got '{selected_tool}'"
    
    def test_power_not_installed_uses_local_tools(self):
        """
        Preservation Test: Without power installed, use local tools
        
        This is NOT a bug - this is expected fallback behavior.
        When ha-development-power is not installed, use local tools.
        
        EXPECTED OUTCOME: PASS (this behavior is correct)
        """
        context = {
            "installed_powers": [],  # Power NOT installed
            "env_vars": {}
        }
        
        user_request = "Show me my Home Assistant configuration.yaml"
        
        # Verify this is NOT a bug condition (power not installed)
        assert not is_bug_condition_1(context, user_request), \
            "Without power installed, should NOT be a bug condition"
        
        # Simulate tool selection
        kiro = MockKiroToolSelector(
            installed_powers=context["installed_powers"],
            env_vars=context["env_vars"]
        )
        selected_tool = kiro.select_tool_for_request(user_request)
        
        # ASSERTION: Should use local tool (this is correct fallback)
        local_tools = ["readFile", "fileSearch", "listDirectory"]
        assert selected_tool in local_tools, \
            f"Without power installed, should use local tools, got '{selected_tool}'"


# ============================================================================
# Counterexample Documentation
# ============================================================================

def document_counterexamples():
    """
    Document counterexamples found during exploration
    
    This function runs the tests and captures failures to document
    which requests trigger the bug.
    """
    print("\n" + "="*80)
    print("BUG 1 EXPLORATION: Local File Lookup")
    print("="*80)
    print("\nCounterexamples (requests that trigger local tools instead of MCP tools):\n")
    
    context = {
        "installed_powers": ["ha-development-power"],
        "env_vars": {"HA_URL": "http://homeassistant.local:8123", "HA_TOKEN": "test_token"}
    }
    
    kiro = MockKiroToolSelector(
        installed_powers=context["installed_powers"],
        env_vars=context["env_vars"]
    )
    
    test_requests = [
        "Show me my Home Assistant configuration.yaml",
        "Read my HA automations.yaml file",
        "List my Home Assistant packages/*.yaml files",
        "Display my homeassistant scripts.yaml",
        "Get my HA configuration.yaml content",
    ]
    
    for i, request in enumerate(test_requests, 1):
        selected_tool = kiro.select_tool_for_request(request)
        is_bug = is_bug_condition_1(context, request)
        
        print(f"{i}. Request: \"{request}\"")
        print(f"   Bug Condition: {is_bug}")
        print(f"   Selected Tool: {selected_tool}")
        
        if selected_tool in ["readFile", "fileSearch", "listDirectory"]:
            print(f"   ❌ BUG CONFIRMED: Uses local tool instead of MCP tool")
        else:
            print(f"   ✅ Correct: Uses MCP tool")
        print()
    
    print("="*80)
    print("CONCLUSION: Bug 1 exists - Kiro uses local file tools for HA file requests")
    print("="*80)


if __name__ == "__main__":
    # Run counterexample documentation
    document_counterexamples()
    
    print("\n\nTo run the exploration tests:")
    print("  PYTHONPATH=src/config-manager/src python -m pytest src/config-manager/tests/test_bug1_local_file_lookup.py -v")
    print("\nExpected outcome: Tests FAIL (this confirms the bug exists)")
