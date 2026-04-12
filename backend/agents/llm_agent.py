"""
LLM Agent using Claude Sonnet for script generation and revision.
"""
import logging
from openai import OpenAI
from openai import APIError as OpenAIAPIError
from openai import RateLimitError
from openai import Timeout as OpenAITimeout
from config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL
import json
from typing import Tuple, Optional
from exceptions import AnthropicCreditError, APITimeoutError, APIAuthenticationError, APIError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LLMAgent:
    """Claude-based agent for script generation and revision."""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        """Initialize OpenRouter client."""
        key = api_key or OPENROUTER_API_KEY
        url = base_url or OPENROUTER_BASE_URL
        self.client = OpenAI(api_key=key, base_url=url)
        self.model = "anthropic/claude-3-haiku"
        self.max_retries = 2

    def write_script(self, raw_text: str, schema: list) -> str:
        """
        Write a Python extraction script for the given document.
        
        Returns Python code string that extracts fields from raw_text.
        The script must assign results to a 'result' dict.
        """
        if not schema:
            logger.warning("Empty schema provided, generating default script")
            schema = [{"name": "field1", "description": "Extracted field", "required": True}]
        
        def get_field_info(f):
            if hasattr(f, 'model_dump'):
                d = f.model_dump()
            elif hasattr(f, 'dict'):
                d = f.dict()
            else:
                d = f
            return d.get('name'), d.get('description', 'N/A')
        
        schema_str = "\n".join([f"  - {name}: {desc}" for f in schema for name, desc in [get_field_info(f)]])
        
        # Escape raw_text to prevent escape sequence issues in prompt
        raw_text_escaped = raw_text[:3000].replace('\\', '\\\\')

        prompt = """Write a Python script to extract the following fields from the document.

Target fields to extract:
""" + schema_str + """

Document text to extract from:
""" + raw_text_escaped + """

IMPORTANT: Output ONLY raw Python code. Do NOT wrap your code in markdown code blocks (no ```python or ```). Start directly with the Python code.

CRITICAL REQUIREMENTS - STRICTLY FOLLOW:
1. Use ONLY 're' module for regex - available as 're' in scope
2. Use ONLY 'json' module for JSON parsing - available as 'json' in scope  
3. Use ONLY 'datetime' module - available as 'datetime' in scope
4. NEVER use: import, from, __import__, eval, exec, open, subprocess, getattr, setattr, lambda
5. If you CANNOT extract a field, set it to None - DO NOT try to import modules or use complex functions
6. The script receives the document text in variable 'raw_text'
7. The script must populate a 'result' dict with the extracted fields
8. Use simple regex patterns: re.search(r'pattern', raw_text)
9. Return None for fields that cannot be found - never try to import or load modules

BAD examples (DO NOT generate - will cause errors):
  - from datetime import datetime
  - import re
  - __import__('json')
  - datetime.datetime.now()
  - eval('...')
  - exec('...')
  - result['x'] = getattr(obj, 'method')
  - result['x'] = lambda x: x+1
  - return result['field']  # return not allowed at top level

GOOD example (output as raw Python, no imports):
result = {{}}
match = re.search(r'INVOICE[:\\s]+([A-Z0-9-]+)', raw_text)
result['invoice_number'] = match.group(1) if match else None
match = re.search(r'Total[:\\s]+\\$?([0-9,]+\\.?[0-9]*)', raw_text)
result['invoice_total'] = match.group(1) if match else None

Output only the Python script, no imports, no explanation, no markdown."""

        for attempt in range(1, self.max_retries + 1):
            try:
                message = self.client.chat.completions.create(
                    model=self.model,
                    max_tokens=2000,
                    messages=[{"role": "user", "content": prompt}]
                )
                
                script = message.choices[0].message.content.strip()
                
                # Clean up markdown from script
                if "Here's the" in script and "script" in script:
                    if "```python" in script:
                        script = script.split("```python")[1].split("```")[0]
                    elif "```" in script:
                        script = script.split("```")[1].split("```")[0]
                
                if script.startswith("```python"):
                    script = script[9:]
                if script.startswith("```"):
                    script = script[3:]
                if script.endswith("```"):
                    script = script[:-3]
                
                logger.info(f"[LLMAgent] Generated script: {script[:300]}...")
                
                # Filter dangerous patterns before validation
                script = self._filter_dangerous_patterns(script)
                
                logger.info(f"[LLMAgent] Script after filtering: {script[:300]}...")
                
                # Validate it's actual Python before returning
                try:
                    import ast
                    ast.parse(script)
                    logger.info(f"Script generated and validated ({len(script)} chars)")
                    return script.strip()
                except SyntaxError as se:
                    logger.warning(f"Generated script has syntax error: {se}, attempting cleanup")
                    # Try to fix common issues
                    lines = script.split('\n')
                    cleaned_lines = []
                    for line in lines:
                        # Skip lines that look like explanations/text
                        if line.strip() and not line.strip().startswith('#'):
                            if 'import ' in line or 'result' in line or 'def ' in line or 're.' in line:
                                cleaned_lines.append(line)
                    if cleaned_lines:
                        script = '\n'.join(cleaned_lines)
                        logger.info(f"Cleaned script: {script[:200]}...")
                    else:
                        logger.error("Could not clean script, will retry")
                
                logger.info(f"Script generated ({len(script)} chars)")
                return script.strip()
            except Exception as e:
                error_type = type(e).__name__
                error_str = str(e).lower()
                
                # Handle specific error types
                if "rate limit" in error_str or "429" in error_str:
                    logger.warning(f"Rate limit hit on script generation attempt {attempt}")
                    if attempt == self.max_retries:
                        raise APIError(str(e), provider="OpenRouter", error_code="RATE_LIMIT")
                elif "timeout" in error_str or "504" in error_str:
                    logger.warning(f"Timeout on script generation attempt {attempt}")
                    if attempt == self.max_retries:
                        raise APITimeoutError("Claude", str(e))
                elif "credit" in error_str or "quota" in error_str or "insufficient" in error_str or "billing" in error_str:
                    logger.error("Insufficient credits for Claude API")
                    raise AnthropicCreditError(str(e))
                elif "authentication" in error_str or "unauthorized" in error_str or "401" in error_str:
                    logger.error("Authentication failed for Claude API")
                    raise APIAuthenticationError("Claude", str(e))
                elif "invalid" in error_str and "model" in error_str:
                    logger.error(f"Invalid model: {e}")
                    raise APIError(str(e), provider="OpenRouter", error_code="INVALID_MODEL")
                elif "400" in error_str or "bad request" in error_str:
                    logger.error(f"Bad request: {e}")
                    raise APIError(str(e), provider="OpenRouter", error_code="BAD_REQUEST")
                else:
                    logger.error(f"OpenRouter API error ({error_type}): {e}")
                    raise APIError(str(e), provider="OpenRouter", error_code="API_ERROR")

    def _extract_python_code(self, response: str) -> str:
        """Extract Python code from LLM response, removing conversational prefixes and markdown."""
        import re
        
        # Try to find code block first
        if "```python" in response:
            code = response.split("```python")[1].split("```")[0]
            return self._fix_trailing_colons(code.strip())
        if "```" in response:
            # Find first code block
            parts = response.split("```")
            if len(parts) >= 3:
                code = parts[1]
                # Skip if it looks like language identifier
                if code.strip().startswith('python'):
                    code = parts[2] if len(parts) > 2 else ""
                return self._fix_trailing_colons(code.strip())
        
        # No code block - extract based on patterns
        lines = response.split('\n')
        code_start = -1
        
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # Skip conversational prefixes
            if stripped.lower().startswith('here is') or stripped.lower().startswith('here\'s'):
                continue
            if 'revised script' in stripped.lower() or 'updated script' in stripped.lower():
                continue
            if stripped.lower().startswith('result ='):
                code_start = i
                break
            if stripped.lower().startswith('import ') or stripped.lower().startswith('def '):
                code_start = i
                break
            # Match lines that look like Python code (assignments, function calls, etc.)
            if re.match(r"^\s*[\w\[\]'\"].*[:=]", stripped) and not stripped.startswith('#'):
                code_start = i
                break
        
        if code_start >= 0:
            extracted = '\n'.join(lines[code_start:])
            return self._fix_trailing_colons(extracted)
        
        # Fallback - return as-is and let syntax validator handle it
        return response

    def _fix_trailing_colons(self, code: str) -> str:
        """Remove trailing colons from non-Python statement lines."""
        lines = code.split('\n')
        fixed_lines = []
        valid_statement_keywords = [
            'if ', 'elif ', 'else:', 'for ', 'while ', 'def ', 'class ',
            'try:', 'except', 'finally:', 'with ', 'async ', 'match ', 'case '
        ]
        
        for line in lines:
            stripped = line.rstrip()
            # If line ends with colon, check if it's a valid statement
            if stripped.endswith(':'):
                # Check if it's a valid Python statement that needs colon
                is_valid = any(stripped.startswith(kw) for kw in valid_statement_keywords)
                # Also check for lambda, which can end with :
                if 'lambda' in stripped:
                    is_valid = True
                    
                if not is_valid:
                    stripped = stripped[:-1]  # Remove trailing colon
            fixed_lines.append(stripped)
        
        return '\n'.join(fixed_lines)

    def _filter_dangerous_patterns(self, script: str) -> str:
        """Remove or replace dangerous patterns in generated scripts."""
        import re
        
        lines = script.split('\n')
        cleaned_lines = []
        
        for line in lines:
            stripped = line.strip()
            
            # Remove entire lines containing dangerous patterns
            # Include __import (without trailing underscores) to catch all variations
            # Also include getattr, setattr, lambda, and other dangerous patterns
            if any(pattern in stripped for pattern in [
                '__import__', '__import', 'import os', 'import sys', 'import subprocess',
                'import socket', 'exec(', 'eval(', 'open(', 'subprocess', 'socket',
                'getattr(', 'setattr(', 'lambda ', '__builtins__', 'compile(',
                'input(', 'print('  # input/print can be used for debug but not needed in extraction
            ]):
                logger.warning(f"[LLMAgent] Filter removing line with dangerous pattern: {line[:80]}...")
                continue
            
            # Remove 'from X import Y' lines entirely
            # Use line.strip() to avoid false positives from variables containing "import"
            if line.strip().startswith('from ') and ('import ' in line.strip()):
                logger.warning(f"[LLMAgent] Filter removing 'from import' line: {line[:80]}...")
                continue
            
            # Additional check: filter lines with eval that might contain dangerous strings
            if 'eval(' in stripped and any(danger in stripped for danger in ['import', '__', 'os.', 'sys.', 'subprocess']):
                logger.warning(f"[LLMAgent] Filter removing eval line with dangerous content: {line[:80]}...")
                continue
            
            # Check for result = eval patterns
            if re.search(r'result\s*=\s*eval\s*\(', stripped, re.IGNORECASE):
                logger.warning(f"[LLMAgent] Filter removing result=eval pattern: {line[:80]}...")
                continue
            
            # Check for getattr/setattr patterns
            if re.search(r'getattr\(|setattr\(', stripped):
                logger.warning(f"[LLMAgent] Filter removing getattr/setattr line: {line[:80]}...")
                continue
            
            # Check for lambda expressions (these can be used to bypass restrictions)
            if re.search(r'=\s*lambda\s', stripped):
                logger.warning(f"[LLMAgent] Filter removing lambda expression: {line[:80]}...")
                continue
            
            # Remove lines with 'return' statements (not allowed at top level of script)
            if stripped.startswith('return '):
                logger.warning(f"[LLMAgent] Filter removing return statement (invalid at top level): {line[:80]}...")
                continue
            
            # Replace dangerous patterns that might be mid-line (less common)
            line = line.replace('__import__', '# removed')
            line = line.replace('__import', '# removed')
            
            cleaned_lines.append(line)
        
        script = '\n'.join(cleaned_lines)
        
        # Fix incorrect datetime usage - datetime.datetime should be just datetime
        if 'datetime.datetime' in script:
            logger.warning(f"[LLMAgent] Fixing datetime.datetime -> datetime")
            script = script.replace('datetime.datetime', 'datetime')
        
        return script

    def revise_script(self, script_body: str, raw_text: str, schema: list, 
                     missing_fields: list, attempt: int) -> str:
        """
        Revise an extraction script based on dLLM feedback.
        """
        if not schema:
            schema = [{"name": "field1", "description": "Extracted field", "required": True}]
        if not missing_fields:
            logger.warning("No missing fields provided, returning original script")
            return script_body
            
        schema_str = "\n".join([f"  - {f['name']}: {f.get('description', 'N/A')}" for f in schema])
        missing_str = ", ".join(missing_fields)

        if attempt == 1:
            guidance = "The document layout may have shifted. Adjust field selectors to match the new format."
        elif attempt == 2:
            guidance = "The previous patch was incomplete. Re-examine the full script and target the right sections."
        else:
            guidance = "This may be a new format variant. Write a completely fresh script with different selectors."

        prompt = f"""Revise this extraction script. The dLLM flagged these fields as missing or incorrect: {missing_str}

Guidance for revision (attempt {attempt}): {guidance}

Current script (KEEP WORKING PARTS - only fix the missing fields):
{script_body}

Document sample:
{raw_text[:2000]}

Target fields:
{schema_str}

IMPORTANT: Output ONLY raw Python code. Do NOT wrap code in markdown code blocks. Start directly with Python.

CRITICAL REQUIREMENTS - STRICTLY FOLLOW:
1. Use ONLY 're' module for regex - available as 're' in scope
2. Use ONLY 'json' module - available as 'json' in scope
3. Use ONLY 'datetime' module - available as 'datetime' in scope
4. NEVER use: import, from, __import__, eval, exec, open, subprocess, getattr, setattr, lambda
5. If you CANNOT extract a field, set it to None - DO NOT try to import modules
6. Keep it simple - use direct regex: re.search(r'pattern', raw_text)
7. The script must populate a 'result' dict
8. Return None for fields that cannot be found - never try to import or load modules
9. IMPORTANT: datetime is a MODULE, not a class. Use datetime.strptime() NOT datetime.datetime.strptime()

BAD examples (DO NOT generate - will cause errors):
  - from datetime import datetime
  - import re
  - __import__('json')
  - eval('...')
  - exec('...')
  - result['x'] = getattr(obj, 'method')
  - result['x'] = lambda x: x+1
  - return result['field']  # return not allowed at top level

NOTE: The current script may already work for some fields. Only modify what's needed to fix the missing fields.

Revised script (raw Python, no imports):"""

        for attempt_num in range(1, self.max_retries + 1):
            try:
                message = self.client.chat.completions.create(
                    model=self.model,
                    max_tokens=2000,
                    messages=[{"role": "user", "content": prompt}]
                )
                
                script = message.choices[0].message.content.strip()
                
                # Clean up markdown and conversational prefixes from revised script
                # Extract only the Python code portion
                script = self._extract_python_code(script)
                
                logger.info(f"[LLMAgent] Revised script: {script[:300]}...")
                
                # Filter out dangerous patterns that would be blocked by ScriptRunner
                script = self._filter_dangerous_patterns(script)
                
                logger.info(f"[LLMAgent] Revised after filter: {script[:300]}...")
                return script.strip()
            except Exception as e:
                error_type = type(e).__name__
                error_str = str(e).lower()
                
                if "rate limit" in error_str or "429" in error_str:
                    logger.warning(f"Rate limit hit on script revision attempt {attempt_num}")
                    if attempt_num == self.max_retries:
                        raise APIError(str(e), provider="OpenRouter", error_code="RATE_LIMIT")
                elif "timeout" in error_str or "504" in error_str:
                    logger.warning(f"Timeout on script revision attempt {attempt_num}")
                    if attempt_num == self.max_retries:
                        raise APITimeoutError("Claude", str(e))
                elif "credit" in error_str or "quota" in error_str or "insufficient" in error_str or "billing" in error_str:
                    logger.error("Insufficient credits for Claude API")
                    raise AnthropicCreditError(str(e))
                elif "authentication" in error_str or "unauthorized" in error_str or "401" in error_str:
                    logger.error("Authentication failed for Claude API")
                    raise APIAuthenticationError("Claude", str(e))
                else:
                    logger.error(f"OpenRouter API error ({error_type}): {e}")
                    raise APIError(str(e), provider="OpenRouter", error_code="API_ERROR")
