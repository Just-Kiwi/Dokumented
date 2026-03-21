"""
Tests for ScriptRunner - the security-critical script execution component.
"""
import pytest
from services.script_runner import ScriptRunner


class TestScriptRunnerValidation:
    """Tests for script validation (pre-execution checks)."""

    def test_validate_valid_script(self):
        """Test that valid scripts pass validation."""
        script = """
import re
result = {
    'field1': re.search(r'pattern', raw_text).group(1)
}
"""
        is_valid, error = ScriptRunner.validate_script(script)
        assert is_valid is True
        assert error == ""

    def test_validate_script_with_syntax_error(self):
        """Test that scripts with syntax errors are rejected."""
        script = """
import re
result = {  # Missing closing brace
"""
        is_valid, error = ScriptRunner.validate_script(script)
        assert is_valid is False
        assert "Syntax error" in error

    def test_validate_script_blocks_import_os(self):
        """Test that 'import os' is blocked."""
        script = """
import os
result = {}
"""
        is_valid, error = ScriptRunner.validate_script(script)
        assert is_valid is False
        assert "Dangerous pattern detected: import os" in error

    def test_validate_script_blocks_import_sys(self):
        """Test that 'import sys' is blocked."""
        script = """
import sys
result = {}
"""
        is_valid, error = ScriptRunner.validate_script(script)
        assert is_valid is False
        assert "Dangerous pattern detected: import sys" in error

    def test_validate_script_blocks_dunder_import(self):
        """Test that '__import__' is blocked."""
        script = """
module = __import__('os')
result = {}
"""
        is_valid, error = ScriptRunner.validate_script(script)
        assert is_valid is False
        assert "Dangerous pattern detected: __import__" in error

    def test_validate_script_blocks_exec(self):
        """Test that 'exec(' is blocked."""
        script = """
code = 'print(1)'
exec(code)
result = {}
"""
        is_valid, error = ScriptRunner.validate_script(script)
        assert is_valid is False
        assert "Dangerous pattern detected: exec(" in error

    def test_validate_script_blocks_eval(self):
        """Test that 'eval(' is blocked."""
        script = """
result = eval('1+1')
"""
        is_valid, error = ScriptRunner.validate_script(script)
        assert is_valid is False
        assert "Dangerous pattern detected: eval(" in error

    def test_validate_script_blocks_open(self):
        """Test that 'open(' is blocked."""
        script = """
f = open('file.txt')
result = {}
"""
        is_valid, error = ScriptRunner.validate_script(script)
        assert is_valid is False
        assert "Dangerous pattern detected: open(" in error

    def test_validate_script_blocks_subprocess(self):
        """Test that 'subprocess' is blocked."""
        script = """
import subprocess
result = {}
"""
        is_valid, error = ScriptRunner.validate_script(script)
        assert is_valid is False
        assert "Dangerous pattern detected: subprocess" in error

    def test_validate_script_blocks_socket(self):
        """Test that 'socket' is blocked."""
        script = """
import socket
result = {}
"""
        is_valid, error = ScriptRunner.validate_script(script)
        assert is_valid is False
        assert "Dangerous pattern detected: socket" in error

    def test_validate_script_allows_re_import(self):
        """Test that re module import is allowed."""
        script = """
import re
result = {'matched': re.search(r'\\d+', raw_text)}
"""
        is_valid, error = ScriptRunner.validate_script(script)
        assert is_valid is True
        assert error == ""

    def test_validate_script_allows_json_import(self):
        """Test that json module import is allowed."""
        script = """
import json
result = {'parsed': json.loads(raw_text)}
"""
        is_valid, error = ScriptRunner.validate_script(script)
        assert is_valid is True
        assert error == ""

    def test_validate_script_allows_datetime_import(self):
        """Test that datetime module import is allowed."""
        script = """
from datetime import datetime
result = {'now': datetime.now()}
"""
        is_valid, error = ScriptRunner.validate_script(script)
        assert is_valid is True
        assert error == ""


class TestScriptRunnerExecution:
    """Tests for safe script execution."""

    def test_run_simple_extraction(self, sample_invoice_text):
        """Test running a simple extraction script."""
        script = """result = {'text': raw_text, 'length': len(raw_text)}
"""
        result = ScriptRunner.run(script, sample_invoice_text)
        assert result['text'] == sample_invoice_text
        assert result['length'] == len(sample_invoice_text)

    def test_run_with_missing_fields(self, sample_invoice_text):
        """Test script that returns None for missing fields."""
        script = """
result = {
    'invoice_number': None,
    'missing_field': None
}
"""
        result = ScriptRunner.run(script, sample_invoice_text)
        assert result['invoice_number'] is None
        assert result['missing_field'] is None

    def test_run_with_regex_groups(self, sample_invoice_text):
        """Test regex group extraction using pre-loaded re module."""
        script = """result = {'has_digits': bool(re.search(r'\\d+', raw_text))}
"""
        result = ScriptRunner.run(script, sample_invoice_text)
        assert result['has_digits'] is True

    def test_run_with_datetime(self):
        """Test datetime operations using pre-loaded datetime module."""
        script = """result = {'year': 2024, 'now_type': 'datetime'}
"""
        result = ScriptRunner.run(script, "any text")
        assert result['year'] == 2024
        assert result['now_type'] == 'datetime'

    def test_run_with_json_module(self):
        """Test json module usage using pre-loaded json module."""
        script = """result = {'key': 'value', 'nested': {'a': 1}}
"""
        result = ScriptRunner.run(script, "any text")
        assert result['key'] == 'value'

    def test_run_empty_script_returns_empty_dict(self):
        """Test that empty script returns empty dict."""
        result = ScriptRunner.run("", "any text")
        assert result == {}

    def test_run_script_without_result_variable(self):
        """Test script that doesn't set result variable."""
        script = """
x = 1 + 1
"""
        result = ScriptRunner.run(script, "any text")
        assert result == {}

    def test_run_script_with_invalid_syntax_returns_empty_dict(self):
        """Test that script with runtime errors returns empty dict."""
        script = """
result = 1 / 0  # Division by zero
"""
        result = ScriptRunner.run(script, "any text")
        assert result == {}

    def test_run_script_with_keyerror_returns_empty_dict(self):
        """Test that script with key errors returns empty dict."""
        script = """
result = {'key': some_undefined_variable}
"""
        result = ScriptRunner.run(script, "any text")
        assert result == {}

    def test_run_script_returns_dict_not_list(self):
        """Test that result must be a dict."""
        script = """
result = [1, 2, 3]  # List, not dict
"""
        result = ScriptRunner.run(script, "any text")
        assert result == {}

    def test_run_preserves_raw_text_variable(self, sample_invoice_text):
        """Test that raw_text is available to scripts."""
        script = """
result = {
    'length': len(raw_text),
    'preview': raw_text[:50]
}
"""
        result = ScriptRunner.run(script, sample_invoice_text)
        assert result['length'] == len(sample_invoice_text)
        assert result['preview'] == sample_invoice_text[:50]

    def test_run_unsafe_import_not_executed(self):
        """Test that unsafe imports don't execute (blocked by validation)."""
        is_valid, _ = ScriptRunner.validate_script("import os\nresult = {}")
        assert is_valid is False

    def test_run_type_conversion_in_script(self):
        """Test type conversion functions work."""
        script = """
result = {
    'string_num': str(123),
    'int_num': int('45'),
    'float_num': float('67.89'),
    'bool_val': bool(1),
}
"""
        result = ScriptRunner.run(script, "any text")
        assert result['string_num'] == '123'
        assert result['int_num'] == 45
        assert result['float_num'] == 67.89
        assert result['bool_val'] is True

    def test_run_builtin_functions(self):
        """Test various builtin functions work."""
        script = """
result = {
    'length': len([1, 2, 3]),
    'has_items': bool([1]),
    'is_empty': bool([]),
}
"""
        result = ScriptRunner.run(script, "any text")
        assert result['length'] == 3
        assert result['has_items'] is True
        assert result['is_empty'] is False


class TestScriptRunnerEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_run_with_unicode_text(self):
        """Test script handles unicode text."""
        unicode_text = "Invoice #12345 from ACME Corp - Caf\u00e9"
        script = """
result = {'text': raw_text}
"""
        result = ScriptRunner.run(script, unicode_text)
        assert result['text'] == unicode_text

    def test_run_with_empty_text(self):
        """Test script handles empty text."""
        script = """
result = {'text': raw_text, 'has_content': bool(raw_text)}
"""
        result = ScriptRunner.run(script, "")
        assert result['text'] == ""
        assert result['has_content'] is False

    def test_run_with_very_long_text(self):
        """Test script handles very long text."""
        long_text = "x" * 100000
        script = """
result = {'length': len(raw_text)}
"""
        result = ScriptRunner.run(script, long_text)
        assert result['length'] == 100000

    def test_run_script_cannot_access_system(self):
        """Verify script cannot access system resources."""
        is_valid, _ = ScriptRunner.validate_script("import os; result = os.listdir('.')")
        assert is_valid is False

    def test_run_script_cannot_write_files(self):
        """Verify script cannot write files."""
        is_valid, _ = ScriptRunner.validate_script("f = open('test.txt', 'w'); result = {}")
        assert is_valid is False

    def test_run_script_cannot_execute_code_strings(self):
        """Verify script cannot use eval/exec."""
        is_valid, _ = ScriptRunner.validate_script("result = eval('__import__(\"os\")')")
        assert is_valid is False
