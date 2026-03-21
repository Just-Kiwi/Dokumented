# Developer Guide - Dokumented

## Architecture Overview

### Two-Model Agent Architecture

```
Document → Parse → Fingerprint (LLM) → Script Lookup/Creation (LLM)
   ↓                                                ↓
 Raw Text                                    Extracted JSON
   ↓                                                ↓
   └─────────────────────ValidationCheck(dLLM)─────┘
                         ↓
                   Field Analysis
                         ↓
        ┌────────────────┬────────────────┐
        ↓                ↓                ↓
    Complete      Low Confidence    High Confidence
                       ↓                ↓
                   LLM Retry      Human Review
                    (Max 3x)
                         ↓
                    Save Result
```

### Component Overview

**Backend (FastAPI + Python)**
- `main.py` - FastAPI routes and WebSocket
- `config.py` - Environment variable loading
- `db/` - Database models and session management
- `agents/` - LLM and dLLM implementations
- `parsers/` - Document format parsing
- `services/` - Extraction pipeline orchestration
- `models/` - Pydantic request/response schemas

**Frontend (React + Vite)**
- `App.jsx` - Main application component
- `components/` - UI panels (Upload, Schema, Results, Monitor, Config)
- `hooks/` - Custom React hooks (useWebSocket)
- `api.js` - Axios HTTP client

**Database (SQLite)**
- `script_library` - Format-specific extraction scripts
- `extraction_results` - Processed documents
- `retry_log` - Retry attempts
- `app_config` - Runtime configuration

## Key Concepts

### 1. Format Fingerprinting

The LLM reads a document and assigns a fingerprint (e.g., "vendor-invoice-tabular"). This is used to:
- Look up existing extraction scripts
- Create new scripts for new formats
- Track format variants

```python
# In agents/llm_agent.py
fingerprint = llm_agent.fingerprint(raw_text)
# Returns: "vendor-invoice-tabular"
```

### 2. Script Generation

LLM writes Python code that extracts fields from raw text. Scripts are:
- Stored in `script_library` table
- Versioned (increments on each revision)
- Tracked for success/failure rates

```python
script_body = llm_agent.write_script(raw_text, schema, fingerprint)
# Example output:
# import re
# result = {
#   'invoice_total': re.search(r'Total.*?\$([0-9.]+)', raw_text).group(1),
#   'vendor_name': re.search(r'From: (.+)', raw_text).group(1),
# }
```

### 3. Field Validation (dLLM)

Mercury 2 performs holistic field checking:
- Reads original document AND extracted JSON
- Identifies missing/uncertain fields
- Assigns confidence scores (0.0-1.0)

```json
{
  "fields": {
    "invoice_total": {
      "status": "filled",
      "value": "1240.00",
      "confidence": 0.98
    },
    "vendor_name": {
      "status": "missing",
      "value": null,
      "confidence": 0.91
    }
  }
}
```

### 4. Retry Logic

Three-attempt ceiling based on failure modes:

**Attempt 1:** Document layout drift
- Adjust field selectors for new layout
- Confidence threshold: unknown

**Attempt 2:** LLM patch incomplete
- Re-examine full script, target right sections
- Confidence threshold: unknown

**Attempt 3:** New format variant
- Treat as entirely new format
- Write fresh script
- Log as new fingerprint candidate

After 3 failed attempts: escalate all missing fields to human review.

### 5. Confidence Routing

```
If confidence > 0.75 (missing/uncertain):
  → Send to Human Gate (field truly absent)

If confidence < 0.75 (missing/uncertain):
  → LLM Retry (script likely failed)
```

## API Design

### REST Endpoints

```
POST /api/config                    → Set API keys
GET  /api/config                    → List configuration
GET  /api/config/{key}              → Get specific config

POST /api/upload                    → Upload & parse document
POST /api/extract                   → Start extraction pipeline
GET  /api/extraction/{result_id}    → Get extraction result
POST /api/extraction/{result_id}/overrides  → Apply human overrides

GET  /api/scripts                   → List all scripts
GET  /api/scripts/{fingerprint}     → Get script details

WS   /ws/status                     → WebSocket events
```

### WebSocket Events

```json
{"event": "fingerprint_assigned", "data": {"fingerprint": "vendor-invoice-tabular"}}
{"event": "script_found", "data": {"version": 3}}
{"event": "script_executed", "data": {"attempt": 1, "fields_found": 8, "fields_total": 10}}
{"event": "dllm_check_complete", "data": {"report": {...}}}
{"event": "retry", "data": {"attempt": 1, "reason": "script_failure", "fields": ["vendor_address"]}}
{"event": "escalated_to_human", "data": {"fields": ["po_number"], "result_id": 42}}
{"event": "complete", "data": {"result_id": 42, "status": "success"}}
```

## Environment Variables

### Required (before first run)
```
ANTHROPIC_API_KEY          # Claude Sonnet API key
MERCURY_API_KEY            # Mercury 2 API key
MERCURY_BASE_URL           # Default: https://api.inceptionlabs.ai/v1
```

### Optional
```
DATABASE_URL               # Default: sqlite:///./dokumented.db
UPLOAD_FOLDER              # Default: ./documents
MAX_RETRIES                # Default: 3
CONFIDENCE_THRESHOLD       # Default: 0.75
```

Note: All can be configured via UI after first run.

## Database Schema

### script_library
```sql
CREATE TABLE script_library (
  id INTEGER PRIMARY KEY,
  fingerprint VARCHAR UNIQUE NOT NULL,
  script_body TEXT NOT NULL,
  version INTEGER DEFAULT 1,
  success_count INTEGER DEFAULT 0,
  fail_count INTEGER DEFAULT 0,
  created_at DATETIME,
  updated_at DATETIME
);
```

### extraction_results
```sql
CREATE TABLE extraction_results (
  id INTEGER PRIMARY KEY,
  filename VARCHAR NOT NULL,
  fingerprint VARCHAR FOREIGN KEY,
  script_version INTEGER NOT NULL,
  raw_text TEXT NOT NULL,
  extracted_json JSON NOT NULL,
  human_overrides JSON,
  status ENUM(complete, partial, failed),
  created_at DATETIME
);
```

### retry_log
```sql
CREATE TABLE retry_log (
  id INTEGER PRIMARY KEY,
  result_id INTEGER FOREIGN KEY,
  attempt_number INTEGER NOT NULL,
  missing_fields JSON,
  dllm_report JSON NOT NULL,
  script_before TEXT NOT NULL,
  script_after TEXT,
  outcome ENUM(resolved, escalated, new_fingerprint),
  created_at DATETIME
);
```

### app_config
```sql
CREATE TABLE app_config (
  id INTEGER PRIMARY KEY,
  key VARCHAR UNIQUE NOT NULL,
  value TEXT NOT NULL,
  created_at DATETIME,
  updated_at DATETIME
);
```

## Development Workflow

### Adding New Document Type Support

1. **Upload sample document** → raw text extracted
2. **LLM fingerprints** → "new-format-name" assigned
3. **LLM writes script** → stored with version 1
4. **Script executes** → produces extracted_json
5. **dLLM validates** → checks completeness
6. **If missing fields** → retry (up to 3x)
7. **If still missing** → human gate for manual input
8. **Script version 1** remains in library for future documents of same format

### Debugging Failed Extractions

1. Check **Agent Monitor** (🤖) for event timeline
2. Review **WebSocket events** in browser console (F12)
3. Check **retry_log** table for:
   - `script_before` / `script_after` comparisons
   - `dllm_report` field analysis
   - `outcome` (resolved / escalated)
4. Verify **API keys** in Settings (⚙️)
5. Check backend logs:
   ```bash
   # Terminal running uvicorn
   ```

## Testing

### Manual Testing

**Test Document Upload:**
```bash
curl -F "file=@path/to/invoice.pdf" http://localhost:8000/api/upload
```

**Test Extraction:**
```bash
curl -X POST http://localhost:8000/api/extract \
  -H "Content-Type: application/json" \
  -d '{
    "filename": "invoice.pdf",
    "raw_text": "...",
    "schema": [{"name": "invoice_total", "description": "...", "required": true}]
  }'
```

**Test Config:**
```bash
curl -X GET http://localhost:8000/api/config
curl -X POST http://localhost:8000/api/config \
  -H "Content-Type: application/json" \
  -d '{"key": "ANTHROPIC_API_KEY", "value": "sk-ant-..."}'
```

### Script Validation

Scripts are validated before execution:
- Compile check (Python syntax)
- Dangerous pattern detection (import os, eval, etc.)
- Restricted to safe libraries: `re`, `json`, `datetime`

```python
# Safe:
import re
result = {'invoice_total': re.search(r'Total: \$([0-9.]+)', raw_text).group(1)}

# Blocked:
import os  # DENIED
open('file.txt')  # DENIED
eval(some_code)  # DENIED
```

## Performance Considerations

### LLM Calls
- **Fingerprint**: ~1 second (50 tokens)
- **Write script**: ~3-5 seconds (1500 tokens)
- **Revise script**: ~3-5 seconds (2000 tokens each retry)

### dLLM Calls
- **Field validation**: ~1 second (750 tokens)
- Runs on every extraction (faster than LLM, good for validation loop)

### Database
- SQLite suitable for single-machine deployments
- For scale-up: migrate to PostgreSQL (schema unchanged)

## Extending the System

### Adding Custom Document Types

Edit frontend `SchemaConfig.jsx` default schema:
```javascript
const [fields, setFields] = useState([
  { name: 'field_name', description: 'Field description', required: true },
  // Add more...
]);
```

### Custom LLM Models

Edit `agents/llm_agent.py`:
```python
self.model = "claude-opus"  # Change from "claude-sonnet-4-6"
```

Update Anthropic API calls to match new model features.

### Custom dLLM Models

Edit `agents/dllm_checker.py`:
```python
self.model = "your-model-name"  # Change model
```

Mercury 2 is OpenAI-compatible, so any OpenAI-compatible model works.

## Common Issues & Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| "API key not working" | Wrong key or expired | Check Settings, re-enter key |
| "Script execution failed" | Syntax error or blocked pattern | Check dLLM report, review script |
| "Missing fields not detected" | dLLM confidence too low | Lower threshold or check query |
| "Database locked" | Multiple processes accessing SQLite | Restart backend, use one instance |
| "WebSocket disconnects" | Network issue or backend down | Check network, restart backend |

## Security Notes

- API keys stored in database (consider encryption for production)
- Scripts sandboxed with limited imports
- No file system access except upload folder
- CORS enabled (configure for production)
- No authentication/authorization (add for multi-user)

## Future Enhancements

- [ ] Batch document processing
- [ ] Advanced script caching
- [ ] Multi-user with authentication
- [ ] OCR for scanned PDFs
- [ ] Export templates
- [ ] Webhook notifications
- [ ] More LLM/dLLM model options
- [ ] Custom extraction rules UI
