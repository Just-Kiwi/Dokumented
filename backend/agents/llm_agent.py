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

        prompt = f"""Write a Python script to extract the following fields from the document.

Target fields to extract:
{schema_str}

Document text to extract from:
{raw_text[:3000]}

IMPORTANT: Output ONLY raw Python code. Do NOT wrap your code in markdown code blocks (no ```python or ```). Start directly with the Python code.

Requirements - STRICTLY FOLLOW:
1. Use ONLY 're' module for regex - available as 're' in scope
2. Use ONLY 'json' module for JSON parsing - available as 'json' in scope  
3. Use ONLY 'datetime' module - available as 'datetime' in scope
4. DO NOT use: import, from, __import__, eval, exec, open, subprocess
5. The script receives the document text in variable 'raw_text'
6. The script must populate a 'result' dict with the extracted fields
7. Use simple regex patterns: re.search(r'pattern', raw_text)
8. Return None for fields that cannot be found
9. Field names should match the target schema exactly
10. Keep the script simple - no complex logic, no helper functions needed

Example of valid script (output as raw Python, no imports):
result = {{}}
match = re.search(r'INVOICE[:\s]+([A-Z0-9-]+)', raw_text)
result['invoice_number'] = match.group(1) if match else None
match = re.search(r'Total[:\s]+\\$?([0-9,]+\\.?[0-9]*)', raw_text)
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

Current script:
{script_body}

Document sample:
{raw_text[:2000]}

Target fields:
{schema_str}

IMPORTANT: Output ONLY raw Python code. Do NOT wrap code in markdown code blocks. Start directly with Python.

Requirements - STRICTLY FOLLOW:
1. Use ONLY 're' module for regex - available as 're' in scope
2. Use ONLY 'json' module - available as 'json' in scope
3. Use ONLY 'datetime' module - available as 'datetime' in scope
4. DO NOT use: import, from, __import__, eval, exec, open, subprocess
5. Keep it simple - use direct regex: re.search(r'pattern', raw_text)
6. The script must populate a 'result' dict
7. Return None for fields that cannot be found

Revised script (raw Python, no imports):"""

        for attempt_num in range(1, self.max_retries + 1):
            try:
                message = self.client.chat.completions.create(
                    model=self.model,
                    max_tokens=2000,
                    messages=[{"role": "user", "content": prompt}]
                )
                
                script = message.choices[0].message.content.strip()
                
                # Clean up markdown from revised script
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
                
                logger.info(f"Script revised ({len(script)} chars)")
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
