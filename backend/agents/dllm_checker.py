"""
dLLM Agent using Mercury 2 for field validation.
"""
import logging
from openai import OpenAI
from openai import APIError as OpenAIAPIError, RateLimitError, Timeout as OpenAITimeout
from config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL
import json
from typing import Optional, Dict, List
from exceptions import MercuryCreditError, APITimeoutError, APIAuthenticationError, APIError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class dLLMChecker:
    """Mercury dLLM-based checker for field completeness validation."""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        """Initialize OpenRouter client."""
        key = api_key or OPENROUTER_API_KEY
        url = base_url or OPENROUTER_BASE_URL
        self.client = OpenAI(api_key=key, base_url=url)
        self.model = "inception/mercury-2"
        self.max_retries = 2

    def check_fields(self, raw_text: str, extracted_json: Dict, schema: List[Dict]) -> Dict:
        """
        Validate which fields are filled, missing, or uncertain.
        
        Returns a dict with field-level analysis including confidence scores.
        Expected format:
        {
            'fields': {
                'field_name': {
                    'status': 'filled' | 'missing' | 'uncertain',
                    'value': extracted_value or null,
                    'confidence': float between 0 and 1
                }
            }
        }
        """
        if not schema:
            logger.warning("Empty schema provided, returning default result")
            return {"fields": {}}
        
        if not extracted_json:
            logger.warning("Empty extracted_json provided")

        def get_field_info(f):
            if hasattr(f, 'model_dump'):
                d = f.model_dump()
            elif hasattr(f, 'dict'):
                d = f.dict()
            else:
                d = f
            return d.get('name'), d.get('description', 'N/A')

        schema_str = "\n".join([f"  - {name}: {desc}" for f in schema for name, desc in [get_field_info(f)]])
        extracted_str = json.dumps(extracted_json, indent=2)

        prompt = f"""Validate field extraction completeness.

Original document (first 2000 chars):
{raw_text[:2000]}

Extracted fields (JSON):
{extracted_str}

Target schema:
{schema_str}

For EACH field in the schema, determine:
1. Is it FILLED (confidently extracted with a value)?
2. Is it MISSING (the document should have had this field but doesn't)?
3. Is it UNCERTAIN (the extraction script may have failed; unclear from the document)?

For each assessment, assign a confidence score (0.0 to 1.0).

Return valid JSON ONLY (no markdown, no code blocks):
{{
  "fields": {{
    "field_name": {{
      "status": "filled|missing|uncertain",
      "value": <extracted_or_expected_value>,
      "confidence": 0.95
    }}
  }}
}}"""

        for attempt in range(1, self.max_retries + 1):
            try:
                message = self.client.chat.completions.create(
                    model=self.model,
                    max_tokens=1500,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3
                )
                
                response_text = message.choices[0].message.content
                if not response_text:
                    logger.warning("Empty response from Mercury API")
                    raise MercuryCreditError("Empty response from Mercury API")
                
                response_text = response_text.strip()
                
                if response_text.startswith("```"):
                    parts = response_text.split("```")
                    if len(parts) >= 2:
                        response_text = parts[1]
                        if response_text.startswith("json"):
                            response_text = response_text[4:]
                        response_text = response_text.strip()
                
                report = json.loads(response_text)
                logger.info(f"dLLM validation complete, {len(report.get('fields', {}))} fields analyzed")
                return report
                
            except Exception as e:
                error_type = type(e).__name__
                error_str = str(e).lower()
                
                if "rate limit" in error_str or "429" in error_str:
                    logger.warning(f"Rate limit hit on dLLM check attempt {attempt}")
                    if attempt == self.max_retries:
                        raise APIError(str(e), provider="Mercury", error_code="RATE_LIMIT")
                elif "timeout" in error_str or "504" in error_str:
                    logger.warning(f"Timeout on dLLM check attempt {attempt}")
                    if attempt == self.max_retries:
                        raise APITimeoutError("Mercury", str(e))
                elif "credit" in error_str or "quota" in error_str or "insufficient" in error_str or "billing" in error_str:
                    logger.error("Insufficient credits for Mercury API")
                    raise MercuryCreditError(str(e))
                elif "authentication" in error_str or "unauthorized" in error_str or "401" in error_str:
                    logger.error("Authentication failed for Mercury API")
                    raise APIAuthenticationError("Mercury", str(e))
                elif "invalid" in error_str and "model" in error_str:
                    logger.error(f"Invalid model: {e}")
                    raise APIError(str(e), provider="Mercury", error_code="INVALID_MODEL")
                elif "json" in error_str:
                    logger.error(f"Failed to parse Mercury response as JSON: {e}")
                    if attempt == self.max_retries:
                        break
                else:
                    logger.error(f"Unexpected error in dLLM check ({error_type}): {e}")
                    if attempt == self.max_retries:
                        break
        
        # Fallback: return a basic report with all fields marked uncertain
        logger.warning("Returning fallback validation report")
        return {
            "fields": {
                field["name"]: {
                    "status": "uncertain",
                    "value": extracted_json.get(field["name"]),
                    "confidence": 0.5
                }
                for field in schema
            }
        }
