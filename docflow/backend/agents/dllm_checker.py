"""
dLLM Agent using Mercury 2 for field validation.
"""
from openai import OpenAI
from config import MERCURY_API_KEY, MERCURY_BASE_URL
import json
from typing import Optional, Dict, List


class dLLMChecker:
    """Mercury dLLM-based checker for field completeness validation."""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        """Initialize Mercury OpenAI-compatible client."""
        key = api_key or MERCURY_API_KEY
        url = base_url or MERCURY_BASE_URL
        self.client = OpenAI(api_key=key, base_url=url)
        self.model = "mercury-coder-small-20b"

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
        schema_str = "\n".join([f"  - {f['name']}: {f.get('description', 'N/A')}" for f in schema])
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

        try:
            message = self.client.chat.completions.create(
                model=self.model,
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            
            response_text = message.choices[0].message.content.strip()
            
            # Clean up response if it has markdown code blocks
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
                response_text = response_text.strip()
            
            report = json.loads(response_text)
            return report
        except json.JSONDecodeError:
            # Fallback: return a basic report if parsing fails
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
        except Exception as e:
            # Fallback on any error
            print(f"dLLM check error: {e}")
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
