# Quick Start Guide

## Initial Setup (Choose One):

### Windows:
```bash
cd dokumented
setup.bat
```

### macOS/Linux:
```bash
cd dokumented
chmod +x setup.sh
./setup.sh
```

## Manual Setup:

### Backend:
```bash
cd backend
python -m venv venv

# Windows:
venv\Scripts\activate

# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

Create `backend/.env`:
```
OPENROUTER_API_KEY=your-openrouter-key-here
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
```

Start backend:
```bash
python -m uvicorn main:app --reload --port 8000
```

### Frontend:
```bash
cd frontend
npm install
npm run dev
```

## Access Points:

| Service | URL |
|---------|-----|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| WebSocket | ws://localhost:8000/ws/status |

## Configuration:

1. Open http://localhost:5173
2. Click **⚙️ Settings** in the top-right
3. Enter your OpenRouter API key:
   - **OPENROUTER_API_KEY** (get from https://openrouter.ai/)
4. Click **Check Configuration** to verify

Keys are stored in the SQLite database (`dokumented.db`).

## Workflow:

1. **Upload** a document (PDF, DOCX, or TXT)
2. **Define Schema** - specify which fields to extract
3. **Start Extraction** - runs the pipeline with retries
4. **Review Results** - see extracted fields
5. **Apply Overrides** - manually fix missing/uncertain fields (if needed)

## Features:

✅ Two-model architecture (LLM + dLLM)
✅ Automatic document fingerprinting
✅ Self-correcting retry loop (up to 3 attempts)
✅ Confidence-based human escalation
✅ WebSocket live event streaming
✅ API key configuration from UI
✅ Script library with format learning

## Troubleshooting:

### "Connection refused" error:
- Ensure backend is running: `python -m uvicorn main:app --reload --port 8000`
- Ensure frontend dev server is running: `npm run dev`

### "API Key not configured" error:
- Go to Settings panel (⚙️)
- Enter and save your API keys
- Check Configuration button will verify they're working

### Script Execution Errors:
- Check the Agent Monitor panel (🤖) for detailed logs
- Review the WebSocket events for error messages
- Ensure the document format matches script expectations

## Technologies:

**Frontend:**
- React 18
- Vite
- Axios (API client)

**Backend:**
- FastAPI
- SQLAlchemy
- Claude Sonnet (Anthropic)
- Mercury 2 (Inception Labs)
- pdfplumber / python-docx (parsing)

**Database:**
- SQLite (zero config)

## API Endpoints:

### Config Management:
- `GET /api/config` - List all config
- `GET /api/config/{key}` - Get specific config
- `POST /api/config` - Set config

### Extraction:
- `POST /api/upload` - Upload document
- `POST /api/extract` - Start extraction
- `GET /api/extraction/{result_id}` - Get results
- `POST /api/extraction/{result_id}/overrides` - Apply human overrides

### Scripts:
- `GET /api/scripts` - List all scripts
- `GET /api/scripts/{fingerprint}` - Get script details

### WebSocket:
- `WS /ws/status` - Live extraction events

---

**For full documentation, see README.md**
