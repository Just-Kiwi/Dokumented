# Dockumented

A two-model agent architecture for converting semi-structured and unstructured documents into fully structured, queryable data.

## Quick Start

### Prerequisites
- Python 3.8+
- Node.js 16+
- API keys: Anthropic (Claude Sonnet) and Inception Labs (Mercury 2)

### Setup Backend

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
```

Create `.env` file in the backend directory:
```
ANTHROPIC_API_KEY=sk-ant-your-key
MERCURY_API_KEY=your-mercury-key
MERCURY_BASE_URL=https://api.inceptionlabs.ai/v1
```

Start the backend:
```bash
python -m uvicorn main:app --reload --port 8000
```

API docs available at: http://localhost:8000/docs

### Setup Frontend

```bash
cd frontend
npm install
```

Start the dev server:
```bash
npm run dev
```

Frontend available at: http://localhost:5173

## Features

### 🤖 Two-Model Architecture
- **LLM (Claude Sonnet)**: Script writing, fingerprinting, reasoning
- **dLLM (Mercury 2)**: Fast field validation, completeness checking

### 📄 Document Processing
- Support for PDF, DOCX, and TXT formats
- Automatic format fingerprinting
- Per-format extraction script library

### 🔄 Intelligent Retry Loop
- Up to 3 automatic retry attempts
- Confidence-based routing to human review
- Persistent failure logging

### 👤 Human-in-the-Loop
- Manual override interface for missing/uncertain fields
- WebSocket live status updates
- Agent monitor dashboard

### ⚙️ Configuration Management
- Configure API keys from web UI
- No need to edit files or restart
- Secure configuration storage in database

## API Endpoints

### Configuration
- `GET /api/config` - List all configuration
- `GET /api/config/{key}` - Get specific config
- `POST /api/config` - Set configuration

### Extraction
- `POST /api/upload` - Upload document
- `POST /api/extract` - Start extraction
- `GET /api/extraction/{result_id}` - Get results
- `POST /api/extraction/{result_id}/overrides` - Apply human overrides

### Script Library
- `GET /api/scripts` - List all scripts
- `GET /api/scripts/{fingerprint}` - Get script details

### WebSocket
- `WS /ws/status` - Live extraction events

## Project Structure

```
docflow/
├── backend/
│   ├── agents/              # LLM and dLLM implementations
│   ├── db/                  # Database models and connection
│   ├── parsers/             # Document parsing
│   ├── services/            # Pipeline and script execution
│   ├── models/              # Pydantic schemas
│   ├── main.py              # FastAPI app
│   ├── config.py            # Configuration
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── components/      # React components
│   │   ├── hooks/           # Custom hooks
│   │   ├── api.js           # API client
│   │   └── App.jsx
│   └── package.json
│
└── .env                     # API keys (create this)
```

## Models & Configuration

### LLM: Claude Sonnet 4.6
- **Purpose**: Reasoning, script generation, fingerprinting
- **API**: Anthropic
- **Env var**: `ANTHROPIC_API_KEY`

### dLLM: Mercury 2
- **Purpose**: Field validation, holistic coverage check
- **API**: Inception Labs (OpenAI-compatible)
- **Env vars**:
  - `MERCURY_API_KEY`
  - `MERCURY_BASE_URL=https://api.inceptionlabs.ai/v1`

## Database

SQLite db automatically created at `docflow.db` with these tables:
- `script_library` - Format-specific extraction scripts
- `extraction_results` - Processed documents
- `retry_log` - Retry attempts and outcomes
- `app_config` - Runtime configuration (API keys, settings)

## Document Types

Optimized for:
- Invoices & receipts (start here)
- Contracts & agreements
- Resumes & CVs
- Medical records
- Research papers

## Configuration from UI

1. Click **⚙️ Settings** in the top-right
2. Enter your Anthropic API key (Claude) and Mercury key
3. Optionally customize Mercury API base URL
4. Click **Check Configuration** to verify
5. Click **Save Configuration**

Keys are encrypted and stored in the database.

## Development

### Running Tests
```bash
cd backend
pytest
```

### Building Frontend for Production
```bash
cd frontend
npm run build
# Output in dist/
```

## Troubleshooting

### API Keys Not Working
- Check keys in browser console (F12)
- Use Settings panel to verify configuration
- Check backend logs: `http://localhost:8000/docs`

### Script Execution Errors
- Scripts are sandboxed and restricted
- Only safe Python imports allowed: `re`, `json`, `datetime`
- Check `/ws/status` WebSocket for detailed error logs

### Document Parsing Issues
- Ensure file format is supported (PDF, DOCX, TXT)
- PDFs must be digital (not scanned images)
- For scanned PDFs, implement OCR layer

## License

MIT

## Support

For issues or questions:
- Check API documentation at endpoints
- Review detailed logs in agent monitor
- Verify configuration settings in database
