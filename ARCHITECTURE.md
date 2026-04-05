# Dokumented System Diagram

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      USER INTERFACE (React)                      │
│  ┌──────────────┐ ┌────────────────┐ ┌──────────────────────┐  │
│  │   Upload     │ │  SchemaConfig  │ │ ResultsViewer        │  │
│  │   Panel      │ │  (Field Defs)  │ │ (Apply Overrides)    │  │
│  └──────────────┘ └────────────────┘ └──────────────────────┘  │
│  ┌─────────────────────────────────┐                            │
│  │   ConfigPanel (⚙️)              │                            │
│  │   - LLM API Key                 │                            │
│  │   - dLLM API Key                │                            │
│  │   - dLLM Base URL               │                            │
│  └─────────────────────────────────┘                            │
│  ┌─────────────────────────────────┐                            │
│  │   AgentMonitor (🤖)             │                            │
│  │   (WebSocket Events)            │                            │
│  └─────────────────────────────────┘                            │
└──────────────────────────────────────────────────────────────────┘
                      ▼ HTTP + WebSocket
┌──────────────────────────────────────────────────────────────────┐
│                   FastAPI Backend (Python)                       │
├──────────────────────────────────────────────────────────────────┤
│  ROUTES:                                                         │
│  POST /api/upload          POST /api/extract                    │
│  GET  /api/config/{key}    POST /api/config                     │
│  GET  /api/extraction/{id} POST /api/extraction/{id}/overrides  │
│  GET  /api/scripts         WS   /ws/status                      │
└──────────────────────────────────────────────────────────────────┘
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│           EXTRACTION PIPELINE (services/pipeline.py)             │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────────┐                                             │
│  │  Parse Document │◄─ [PDF/DOCX/TXT]                          │
│  │  (doc_parser)   │                                             │
│  └────────┬────────┘                                             │
│           │ raw_text                                             │
│           ▼                                                       │
│  ┌────────────────────────────────────────────┐                 │
│  │  Script Lookup / Creation                  │                 │
│  │  ├─ Query script_library                   │                 │
│  │  └─ If not found: LLM writes new script   │                 │
│  └────────┬───────────────────────────────────┘                 │
│           │ script_body                                          │
│           ▼                                                       │
│  ┌────────────────────────────────────────────┐                 │
│  │  Script Execution Loop (max 3 attempts)   │                 │
│  │  ┌────────────────────────────────────┐   │                 │
│  │  │ 1. Execute Script                   │   │                 │
│  │  │    (services/script_runner.py)      │   │                 │
│  │  │    ↓                                │   │                 │
│  │  │ 2. dLLM Field Validation            │   │                 │
│  │  │    (agents/dllm_checker.py)          │   │                 │
│  │  │    ├─ Missing fields?               │   │                 │
│  │  │    └─ Confidence score              │   │                 │
│  │  │       ├─ High (>0.75) →Human Gate  │   │                 │
│  │  │       └─ Low  (<0.75) →LLM Retry   │   │                 │
│  │  │    ↓                                │   │                 │
│  │  │ 3. If Low Confidence & Attempts <3:│   │                 │
│  │  │    LLM revises script               │   │                 │
│  │  │    (Try next iteration)             │   │                 │
│  │  │    ↓                                │   │                 │
│  │  │ 4. If Attempts = 3 or High Conf:  │   │                 │
│  │  │    Exit loop → Save result          │   │                 │
│  │  └────────────────────────────────────┘   │                 │
│  └────────┬───────────────────────────────────┘                 │
│           │                                                       │
│           ▼                                                       │
│  ┌────────────────────────────────────────────┐                 │
│  │  Save Result                               │                 │
│  │  ├─ extraction_results table               │                 │
│  │  ├─ retry_log table (if attempts > 1)    │                 │
│  │  └─ Update script stats                    │                 │
│  └────────┬───────────────────────────────────┘                 │
│           │                                                       │
│           ▼                                                       │
│  ┌────────────────────────────────────────────┐                 │
│  │  Send WebSocket Events                     │                 │
│  │  - script_found / script_written           │                 │
│  │  - script_executed                         │                 │
│  │  - dllm_check_complete                     │                 │
│  │  - retry (if needed)                       │                 │
│  │  - escalated_to_human / complete           │                 │
│  └────────────────────────────────────────────┘                 │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│                      SQLite Database                             │
├──────────────────────────────────────────────────────────────────┤
│  ┌──────────────────────┐  ┌─────────────────────┐             │
│  │ script_library       │  │ extraction_results  │             │
│  │ ─────────────────    │  │ ──────────────────  │             │
│  │ script_body          │  │ filename            │             │
│  │ version              │  │ script_id (FK)      │             │
│  │ success_count        │  │ script_version      │             │
│  │ fail_count           │  │ raw_text            │             │
│  │ created_at/updated_at│  │ extracted_json      │             │
│  └──────────────────────┘  │ human_overrides     │             │
│                             │ status              │             │
│                             │ created_at          │             │
│                             └─────────────────────┘             │
│  ┌──────────────────────┐  ┌─────────────────────┐             │
│  │ retry_log            │  │ app_config          │             │
│  │ ──────────────────   │  │ ──────────────────  │             │
│  │ result_id (FK)       │  │ key (UNIQUE)        │             │
│  │ attempt_number       │  │ value               │             │
│  │ missing_fields       │  │ created_at/updated_at               │
│  │ dllm_report          │  │                     │             │
│  │ script_before        │  │ Config keys:        │             │
│  │ script_after         │  │ - OPENROUTER_API_KEY│             │
│  │ outcome              │  │ - OPENROUTER_BASE_URL             │
│  │ created_at           │  │ - MAX_RETRIES      │             │
│  └──────────────────────┘  │ - CONFIDENCE_THRESHOLD            │
│                             └─────────────────────┘             │
└──────────────────────────────────────────────────────────────────┘
```

## Data Flow: Complete Extraction Journey

```
1. USER UPLOADS DOCUMENT
   │
   └─→ POST /api/upload
       │
       ├─ Save file to ./documents
       ├─ Parse with DocumentParser (PDF/DOCX/TXT)
       ├─ Extract raw_text
       └─ Return to frontend

2. USER DEFINES EXTRACTION SCHEMA
   │
   └─→ Schema: [{"name": "invoice_total", "required": true}, ...]

3. USER CLICKS "START EXTRACTION"
   │
   └─→ POST /api/extract
       │
       ├─ Get API keys from app_config table
       ├─ Initialize LLMAgent and dLLMChecker
       │
       └─→ PIPELINE.extract():
           │
           ├─ Step 1: Script Lookup
           │  ├─ Query: SELECT * FROM script_library 
           │  │          ORDER BY success_count DESC
           │  ├─ If found: Use existing script (emit: script_found)
           │  └─ If not: LLM writes new script (emit: script_written)
           │
           ├─ Step 2-7: Execute with Retry Loop
           │  │
           │  └─ For attempt = 1 to 3:
           │     │
           │     ├─ Execute Script
           │     │  └─ ScriptRunner.run(script_body, raw_text)
           │     │  └─ Returns: {invoice_total: "1240.00", ...}
           │     │  └─ Emit: script_executed event
           │     │
           │     ├─ dLLM Validation
           │     │  └─ Mercury validates field completeness
           │     │  └─ Returns: {fields: {invoice_total: {status: 
           │     │             "filled", confidence: 0.98}, ...}}
           │     │  └─ Emit: dllm_check_complete event
           │     │
           │     ├─ Analyze Missing Fields
           │     │  ├─ High confidence (>0.75) missing?
           │     │  │  └─ → Will escalate to human
           │     │  └─ Low confidence (<0.75) missing?
           │     │     └─ → Attempt retry (if attempt < 3)
           │     │
           │     └─ If retry needed:
           │        ├─ Emit: retry event
           │        ├─ LLM revises script based on failures
           │        ├─ Log to retry_log table
           │        └─ Continue loop with new script
           │
           ├─ Step 8: Save Result
           │  ├─ INSERT INTO extraction_results:
           │  │  filename, script_id, script_version,
           │  │  raw_text, extracted_json, status
           │  │
           │  ├─ If escalation needed:
           │  │  └─ Emit: escalated_to_human event
           │  │
           │  └─ Update script_library stats:
           │     SUCCESS_COUNT or FAIL_COUNT++
           │
           └─ Emit: complete event with result_id

4. FRONTEND RECEIVES RESULT
   │
   └─ Display extracted fields
   └─ Show missing/uncertain fields for human review
   └─ Allow manual overrides

5. HUMAN REVIEW (IF NEEDED)
   │
   └─→ POST /api/extraction/{result_id}/overrides
       │
       ├─ Merge human overrides into extracted_json
       ├─ Update extraction_results.human_overrides
       ├─ Set status = complete
       └─ Save to database
```

## Confidence-Based Routing

```
┌─ dLLM Field Report
│  └─ Field Status: "filled", "missing", or "uncertain"
│  └─ Confidence: 0.0 to 1.0
│
└─ Decision Tree:
   │
   ├─ If status = "filled" AND confidence > 0.5:
   │  └─ ✓ Field complete
   │
   ├─ If status = "missing" OR "uncertain":
   │  │
   │  ├─ If confidence > CONFIDENCE_THRESHOLD (0.75):
   │  │  └─ 🚪 HIGH CONFIDENCE MISSING
   │  │     ├─ Document truly lacks this field
   │  │     └─ → Send to Human Gate
   │  │
   │  └─ If confidence ≤ CONFIDENCE_THRESHOLD:
   │     └─ 🔄 LOW CONFIDENCE MISSING
   │        ├─ Script may have failed
   │        └─ → LLM Retry (if attempts < 3)
```

## Retry Strategy

```
Attempt 1: Layout Drift
├─ Assumption: Document format changed but same type
├─ Action: LLM adjusts regex patterns
├─ Provided: Gap list + document sample
└─ Goal: Adapt to new layout variations

Attempt 2: Incomplete Patch
├─ Assumption: Previous patch didn't fully solve problem
├─ Action: LLM re-examines entire script
├─ Provided: Previous patch + still-failing fields
└─ Goal: Identify and fix oversights

Attempt 3: New Variant
├─ Assumption: Document is genuinely new format
├─ Action: LLM writes completely fresh script
├─ Provided: Full document + field schema
└─ Goal: Treat as new format variant
└─ Note: Logged as new script version

After Attempt 3: Escalate
└─ All missing fields sent to human gate
└─ Failed script attempt flagged in retry_log
└─ Scripts retained for manual review
```

## File Organization

```
Frontend File Structure:
src/
 ├─ App.jsx           # Main container
 ├─ App.css           # Global styles
 ├─ api.js            # HTTP/WS client
 ├─ main.jsx          # React entry point
 │
 ├─ components/
 │  ├─ Upload/        # Drop zone, file parsing
 │  ├─ SchemaConfig/  # Field definition form
 │  ├─ ResultsViewer/ # Results display + overrides
 │  ├─ AgentMonitor/  # Event timeline
 │  └─ ConfigPanel/   # API key configuration
 │
 └─ hooks/
    └─ useWebSocket.js # WebSocket state management

Backend File Structure:
├─ main.py            # FastAPI routes
├─ config.py          # Config loading
│
├─ db/
│  ├─ database.py     # SQLAlchemy setup
│  └─ models.py       # ORM models
│
├─ agents/
│  ├─ llm_agent.py    # Claude Sonnet wrapper
│  └─ dllm_checker.py # Mercury 2 validator
│
├─ parsers/
│  └─ doc_parser.py   # PDF/DOCX/TXT parsing
│
└─ services/
   ├─ pipeline.py     # Main orchestration
   └─ script_runner.py # Safe script execution
```

---

This architecture ensures:
- ✅ **Modularity**: Each component has clear responsibility
- ✅ **Scalability**: Can add new document types via script library
- ✅ **Resilience**: Retry logic handles common failures
- ✅ **Transparency**: WebSocket events show everything happening
- ✅ **Flexibility**: API key configuration at runtime
- ✅ **Safety**: Sandboxed script execution, limited imports