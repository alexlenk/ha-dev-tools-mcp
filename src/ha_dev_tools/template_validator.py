"""Template validation and error formatting utilities for Home Assistant templates."""

import re
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Tuple
from jinja2 import Environment, TemplateSyntaxError


@dataclass
class TemplateError:
    """Structured template error information."""
    error_type: str
    message: str
    line: Optional[int] = None
    column: Optional[int] = None
    context: Optional[str] = None
    template_excerpt: Optional[List[str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "error_type": self.error_type,
            "message": self.message
        }
        if self.line is not None:
            result["line"] = self.line
        if self.column is not None:
            result["column"] = self.column
        if self.context is not None:
            result["context"] = self.context
        if self.template_excerpt is not None:
            result["template_excerpt"] = self.template_excerpt
        return result


@dataclass
class ValidationResult:
    """Result of template validation."""
    valid: bool
    error: Optional[TemplateError] = None
    warnings: Optional[List[str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {"valid": self.valid}
        if self.error:
            result["error"] = self.error.to_dict()
        if self.warnings:
            result["warnings"] = self.warnings
        return result


def extract_entity_references(template: str) -> List[str]:
    """Extract entity IDs from template string.
    
    Matches patterns:
    - states('entity.id') or states("entity.id")
    - state_attr('entity.id', ...) or state_attr("entity.id", ...)
    - is_state('entity.id', ...) or is_state("entity.id", ...)
    - states.domain.entity_name
    
    Args:
        template: Jinja2 template string to analyze
        
    Returns:
        Sorted list of unique entity IDs found in template
    """
    entity_ids = set()
    
    # Pattern 1: Function calls with entity ID as first argument
    # Matches: states('entity.id'), state_attr('entity.id', 'attr'), etc.
    function_pattern = r"(?:states|state_attr|is_state|is_state_attr)\s*\(\s*['\"]([a-z_]+\.[a-z0-9_]+)['\"]"
    for match in re.finditer(function_pattern, template, re.IGNORECASE):
        entity_ids.add(match.group(1))
    
    # Pattern 2: Direct state access via states.domain.entity
    # Matches: states.sensor.temperature
    direct_pattern = r"states\.([a-z_]+)\.([a-z0-9_]+)"
    for match in re.finditer(direct_pattern, template, re.IGNORECASE):
        entity_id = f"{match.group(1)}.{match.group(2)}"
        entity_ids.add(entity_id)
    
    return sorted(list(entity_ids))


def validate_template_syntax(template: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """Validate template syntax without executing.
    
    Args:
        template: Jinja2 template string to validate
        
    Returns:
        Tuple of (is_valid, error_dict)
        - (True, None) if valid
        - (False, error_dict) if invalid with error details
    """
    try:
        # Create Jinja2 environment (no HA context needed for syntax check)
        env = Environment()
        
        # Parse template (syntax check only, no execution)
        env.parse(template)
        
        return (True, None)
        
    except TemplateSyntaxError as e:
        # Extract error information from Jinja2 exception
        error_dict = {
            "error_type": "TemplateSyntaxError",
            "message": str(e.message) if hasattr(e, 'message') else str(e),
            "line": e.lineno if hasattr(e, 'lineno') else None,
        }
        
        # Add context line if line number is available
        if e.lineno:
            context = _extract_error_line(template, e.lineno)
            if context:
                error_dict["context"] = context
        
        return (False, error_dict)
        
    except Exception as e:
        # Unexpected error during parsing
        error_dict = {
            "error_type": type(e).__name__,
            "message": str(e)
        }
        return (False, error_dict)


def format_template_error(error: Exception, template: str) -> Dict[str, Any]:
    """Format Jinja2 exception into structured error dictionary.
    
    Args:
        error: Exception raised during template processing
        template: Original template string
        
    Returns:
        Structured error dictionary with all available diagnostic information
    """
    error_dict = {
        "error_type": type(error).__name__,
        "message": str(error)
    }
    
    # Extract line number if available
    if hasattr(error, 'lineno') and error.lineno:
        error_dict["line"] = error.lineno
        
        # Extract the problematic line
        lines = template.split('\n')
        if 1 <= error.lineno <= len(lines):
            error_dict["context"] = lines[error.lineno - 1]
            
            # For multi-line templates, include surrounding context
            if len(lines) > 1:
                error_dict["template_excerpt"] = _extract_template_excerpt(
                    lines, error.lineno
                )
    
    # Extract column number if available
    if hasattr(error, 'colno') and error.colno:
        error_dict["column"] = error.colno
    
    return error_dict


def _extract_template_excerpt(
    lines: List[str], 
    error_line: int, 
    context_lines: int = 2
) -> List[str]:
    """Extract surrounding lines for error context.
    
    Args:
        lines: All template lines
        error_line: Line number with error (1-indexed)
        context_lines: Number of lines to show before/after error
        
    Returns:
        List of formatted lines with line numbers and error marker
    """
    excerpt = []
    start = max(1, error_line - context_lines)
    end = min(len(lines), error_line + context_lines)
    
    for i in range(start, end + 1):
        line_text = lines[i - 1]
        if i == error_line:
            excerpt.append(f"Line {i}: {line_text}  <-- ERROR")
        else:
            excerpt.append(f"Line {i}: {line_text}")
    
    return excerpt


def _extract_error_line(template: str, line_number: int) -> Optional[str]:
    """Extract specific line from template.
    
    Args:
        template: Template string
        line_number: Line number to extract (1-indexed)
        
    Returns:
        The line at the specified line number, or None if out of range
    """
    lines = template.split('\n')
    if 1 <= line_number <= len(lines):
        return lines[line_number - 1]
    return None


def format_entity_validation_warnings(missing_entities: List[str]) -> str:
    """Format list of missing entities into user-friendly warning message.
    
    Args:
        missing_entities: List of entity IDs that don't exist in Home Assistant
        
    Returns:
        Formatted warning string
    """
    if not missing_entities:
        return ""
    
    if len(missing_entities) == 1:
        return f"Warning: The following entity does not exist: {missing_entities[0]}"
    
    entity_list = ", ".join(missing_entities)
    return f"Warning: The following entities do not exist: {entity_list}"
