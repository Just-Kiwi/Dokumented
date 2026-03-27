"""
LLM Agent using Claude Sonnet for fingerprinting and script generation.
"""
import logging
from openai import OpenAI
from openai import APIError as OpenAIAPIError, RateLimitError, Timeout as OpenAITimeout
from config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL
import json
from typing import Tuple, Optional
from exceptions import AnthropicCreditError, APITimeoutError, APIAuthenticationError, APIError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LLMAgent:
    """Claude-based agent for fingerprinting and script generation."""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        """Initialize OpenRouter client."""
        key = api_key or OPENROUTER_API_KEY
        url = base_url or OPENROUTER_BASE_URL
        self.client = OpenAI(api_key=key, base_url=url)
        self.model = "anthropic/claude-3.5-sonnet"
        self.max_retries = 2

    def fingerprint(self, raw_text: str) -> str:
        """
        Read a document and return a format fingerprint string.
        Example output: "vendor-invoice-tabular", "employment-contract-uk"
        """
        prompt = f"""Analyze this document and return a concise format fingerprint (2-4 words, hyphenated).
        
Examples:
- "vendor-invoice-tabular" for a structured invoice with vendor info and line items
- "employment-contract-uk" for a UK employment agreement
- "medical-form-structured" for a standardized medical form
- "receipt-tabular" for a simple receipt with line items

Document text (first 1000 chars):
{raw_text[:1000]}

Return ONLY the fingerprint string, nothing else."""

        for attempt in range(1, self.max_retries + 1):
            try:
                message = self.client.chat.completions.create(
                    model=self.model,
                    max_tokens=50,
                    messages=[{"role": "user", "content": prompt}]
                )
                
                fingerprint = message.choices[0].message.content.strip().lower()
                logger.info(f"Fingerprint generated: {fingerprint}")
                return fingerprint
            except RateLimitError as e:
                logger.warning(f"Rate limit hit on fingerprint attempt {attempt}, retrying...")
                if attempt == self.max_retries:
                    raise APIError(str(e), provider="OpenRouter", error_code="RATE_LIMIT")
            except OpenAITimeout as e:
                logger.warning(f"Timeout on fingerprint attempt {attempt}, retrying...")
                if attempt == self.max_retries:
                    raise APITimeoutError("Claude", str(e))
            except OpenAIAPIError as e:
                error_str = str(e).lower()
                if "credit" in error_str or "quota" in error_str or "insufficient" in error_str or "billing" in error_str:
                    logger.error("Insufficient credits for Claude API")
                    raise AnthropicCreditError(str(e))
                if "authentication" in error_str or "unauthorized" in error_str:
                    logger.error("Authentication failed for Claude API")
                    raise APIAuthenticationError("Claude", str(e))
                logger.error(f"OpenRouter API error: {e}")
                raise APIError(str(e), provider="OpenRouter", error_code="API_ERROR")

    def write_script(self, raw_text: str, schema: list, fingerprint: str) -> str:
        """
        Write a Python extraction script for the given document format.
        
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

        prompt = f"""Write a Python script to extract fields from a document of format: {fingerprint}

Target fields to extract:
{schema_str}

Document text to extract from:
{raw_text[:3000]}

Requirements:
1. Return a Python script that uses only built-in libraries (re, json, datetime)
2. The script receives the document text in variable 'raw_text'
3. The script must populate a 'result' dict with the extracted fields
4. Use string operations and regex to find field values
5. Return None for fields that cannot be found
6. Field names should match the target schema exactly

Example structure:
```python
import re
import json
from datetime import datetime

# Your extraction logic here
# ...

result = {{
    'field_name_1': extracted_value,
    'field_name_2': extracted_value,
    'field_name_3': None
}}
```

Write only the Python script, no explanation."""

        for attempt in range(1, self.max_retries + 1):
            try:
                message = self.client.chat.completions.create(
                    model=self.model,
                    max_tokens=2000,
                    messages=[{"role": "user", "content": prompt}]
                )
                
                script = message.choices[0].message.content.strip()
                if script.startswith("```python"):
                    script = script[9:]
                if script.startswith("```"):
                    script = script[3:]
                if script.endswith("```"):
                    script = script[:-3]
                
                logger.info(f"Script generated ({len(script)} chars)")
                return script.strip()
            except RateLimitError as e:
                logger.warning(f"Rate limit hit on script generation attempt {attempt}")
                if attempt == self.max_retries:
                    raise APIError(str(e), provider="OpenRouter", error_code="RATE_LIMIT")
            except OpenAITimeout as e:
                logger.warning(f"Timeout on script generation attempt {attempt}")
                if attempt == self.max_retries:
                    raise APITimeoutError("Claude", str(e))
            except OpenAIAPIError as e:
                error_str = str(e).lower()
                if "credit" in error_str or "quota" in error_str or "insufficient" in error_str or "billing" in error_str:
                    logger.error("Insufficient credits for Claude API")
                    raise AnthropicCreditError(str(e))
                if "authentication" in error_str or "unauthorized" in error_str:
                    logger.error("Authentication failed for Claude API")
                    raise APIAuthenticationError("Claude", str(e))
                logger.error(f"OpenRouter API error: {e}")
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
```python
{script_body}
```

Document sample:
{raw_text[:2000]}

Target fields:
{schema_str}

Requirements:
1. Return ONLY revised Python code
2. Keep the same structure (result dict with field names)
3. Adjust regex patterns or string operations to locate missing fields
4. Return None for fields that truly cannot be found
5. Use only re, json, datetime libraries

Revised script:"""

        for attempt_num in range(1, self.max_retries + 1):
            try:
                message = self.client.chat.completions.create(
                    model=self.model,
                    max_tokens=2000,
                    messages=[{"role": "user", "content": prompt}]
                )
                
                script = message.choices[0].message.content.strip()
                if script.startswith("```python"):
                    script = script[9:]
                if script.startswith("```"):
                    script = script[3:]
                if script.endswith("```"):
                    script = script[:-3]
                
                logger.info(f"Script revised ({len(script)} chars)")
                return script.strip()
            except RateLimitError as e:
                logger.warning(f"Rate limit hit on script revision attempt {attempt_num}")
                if attempt_num == self.max_retries:
                    raise APIError(str(e), provider="OpenRouter", error_code="RATE_LIMIT")
            except OpenAITimeout as e:
                logger.warning(f"Timeout on script revision attempt {attempt_num}")
                if attempt_num == self.max_retries:
                    raise APITimeoutError("Claude", str(e))
            except OpenAIAPIError as e:
                error_str = str(e).lower()
                if "credit" in error_str or "quota" in error_str or "insufficient" in error_str or "billing" in error_str:
                    logger.error("Insufficient credits for Claude API")
                    raise AnthropicCreditError(str(e))
                if "authentication" in error_str or "unauthorized" in error_str:
                    logger.error("Authentication failed for Claude API")
                    raise APIAuthenticationError("Claude", str(e))
                logger.error(f"OpenRouter API error: {e}")
                raise APIError(str(e), provider="OpenRouter", error_code="API_ERROR")
