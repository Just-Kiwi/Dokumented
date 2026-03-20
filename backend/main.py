"""
FastAPI application for DocFlow.
Main entry point with all routes and WebSocket support.
"""
import json
from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from db.database import get_db, init_db
from db.models import ExtractionResult, ScriptLibrary, AppConfig
from models.schemas import (
    ConfigUpdate, ConfigResponse, SchemaRequest, ExtractRequest,
    HumanOverridesRequest, ExtractionReportResponse, WSEvent
)
from services.pipeline import ExtractionPipeline
from parsers.doc_parser import DocumentParser
from config import UPLOAD_FOLDER
import os
import asyncio
from datetime import datetime
from typing import Dict, List, Optional

# Initialize database
init_db()

app = FastAPI(title="DocFlow", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket manager for broadcasting events
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"Broadcast error: {e}")

manager = ConnectionManager()

# Global state for current extraction
current_events_queue = []


def emit_event(event: dict):
    """Add event to queue for WebSocket broadcasting."""
    current_events_queue.append(event)
    asyncio.create_task(manager.broadcast(event))


# ============================================================================
# CONFIG ENDPOINTS
# ============================================================================

@app.post("/api/config", response_model=ConfigResponse)
def set_config(update: ConfigUpdate, db: Session = Depends(get_db)):
    """Set a configuration value (API keys, settings)."""
    
    # Restricted keys that can be set
    allowed_keys = [
        "ANTHROPIC_API_KEY",
        "MERCURY_API_KEY",
        "MERCURY_BASE_URL",
        "MAX_RETRIES",
        "CONFIDENCE_THRESHOLD"
    ]
    
    if update.key not in allowed_keys:
        raise HTTPException(status_code=400, detail=f"Key '{update.key}' not allowed")

    # Check if exists
    config = db.query(AppConfig).filter_by(key=update.key).first()
    if config:
        config.value = update.value
        config.updated_at = datetime.utcnow()
    else:
        config = AppConfig(key=update.key, value=update.value)
        db.add(config)

    db.commit()
    db.refresh(config)
    return config


@app.get("/api/config/{key}", response_model=ConfigResponse)
def get_config(key: str, db: Session = Depends(get_db)):
    """Get a configuration value."""
    allowed_keys = [
        "ANTHROPIC_API_KEY",
        "MERCURY_API_KEY",
        "MERCURY_BASE_URL",
        "MAX_RETRIES",
        "CONFIDENCE_THRESHOLD"
    ]
    
    if key not in allowed_keys:
        raise HTTPException(status_code=400, detail=f"Key '{key}' not allowed")
    
    config = db.query(AppConfig).filter_by(key=key).first()
    if not config:
        raise HTTPException(status_code=404, detail=f"Config '{key}' not found")
    return config


@app.get("/api/config")
def list_config(db: Session = Depends(get_db)):
    """List all configuration values (excluding sensitive keys)."""
    configs = db.query(AppConfig).all()
    safe_configs = {}
    
    # Don't return API key values, only confirm they exist
    sensitive_keys = ["ANTHROPIC_API_KEY", "MERCURY_API_KEY"]
    
    for config in configs:
        if config.key in sensitive_keys:
            safe_configs[config.key] = {"exists": bool(config.value), "updated_at": config.updated_at}
        else:
            safe_configs[config.key] = {"value": config.value, "updated_at": config.updated_at}
    
    return safe_configs


# ============================================================================
# EXTRACTION ENDPOINTS
# ============================================================================

@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload a document and return raw text."""
    
    # Save file
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    
    with open(file_path, 'wb') as f:
        content = await file.read()
        f.write(content)
    
    # Parse document
    try:
        raw_text = DocumentParser.parse(file_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Parse error: {str(e)}")
    
    return {
        "filename": file.filename,
        "raw_text": raw_text[:10000],  # Return first 10k chars for preview
        "full_text_length": len(raw_text)
    }


@app.post("/api/extract")
async def extract(request: ExtractRequest, db: Session = Depends(get_db)):
    """Extract fields from a document."""
    
    # Get API keys from config or use defaults
    llm_key = None
    dllm_key = None
    dllm_url = None
    
    llm_config = db.query(AppConfig).filter_by(key="ANTHROPIC_API_KEY").first()
    if llm_config and llm_config.value:
        llm_key = llm_config.value
    
    dllm_config = db.query(AppConfig).filter_by(key="MERCURY_API_KEY").first()
    if dllm_config and dllm_config.value:
        dllm_key = dllm_config.value
    
    url_config = db.query(AppConfig).filter_by(key="MERCURY_BASE_URL").first()
    if url_config:
        dllm_url = url_config.value
    
    # Create pipeline
    pipeline = ExtractionPipeline(
        db,
        llm_api_key=llm_key,
        dllm_api_key=dllm_key,
        dllm_base_url=dllm_url
    )
    
    # Clear events
    current_events_queue.clear()
    
    # Run extraction
    try:
        result_id = await pipeline.extract(
            request.filename,
            request.raw_text,
            request.schema or [],
            events_callback=emit_event
        )
        
        return {"result_id": result_id, "status": "started"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction error: {str(e)}")


@app.get("/api/extraction/{result_id}", response_model=ExtractionReportResponse)
def get_extraction(result_id: int, db: Session = Depends(get_db)):
    """Get an extraction result."""
    result = db.query(ExtractionResult).filter_by(id=result_id).first()
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")
    
    # Get missing fields from dLLM report (if available)
    missing_fields = []
    dllm_report = {}
    
    return ExtractionReportResponse(
        result_id=result.id,
        filename=result.filename,
        fingerprint=result.fingerprint,
        status=result.status.value,
        extracted_json=result.extracted_json,
        missing_fields=missing_fields,
        dllm_report=dllm_report
    )


@app.post("/api/extraction/{result_id}/overrides")
def apply_overrides(result_id: int, request: HumanOverridesRequest, db: Session = Depends(get_db)):
    """Apply human overrides to missing/uncertain fields."""
    
    result = db.query(ExtractionResult).filter_by(id=result_id).first()
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")
    
    pipeline = ExtractionPipeline(db)
    overrides_dict = {o.field_name: o.value for o in request.overrides}
    
    final_json = pipeline.apply_human_overrides(result_id, overrides_dict)
    
    return {
        "result_id": result_id,
        "extracted_json": final_json,
        "status": "complete"
    }


# ============================================================================
# SCRIPT LIBRARY ENDPOINTS
# ============================================================================

@app.get("/api/scripts")
def list_scripts(db: Session = Depends(get_db)):
    """List all scripts in the library."""
    scripts = db.query(ScriptLibrary).all()
    return [
        {
            "id": s.id,
            "fingerprint": s.fingerprint,
            "version": s.version,
            "success_count": s.success_count,
            "fail_count": s.fail_count,
            "created_at": s.created_at,
            "updated_at": s.updated_at
        }
        for s in scripts
    ]


@app.get("/api/scripts/{fingerprint}")
def get_script(fingerprint: str, db: Session = Depends(get_db)):
    """Get a script by fingerprint."""
    script = db.query(ScriptLibrary).filter_by(fingerprint=fingerprint).first()
    if not script:
        raise HTTPException(status_code=404, detail="Script not found")
    
    return {
        "fingerprint": script.fingerprint,
        "script_body": script.script_body,
        "version": script.version,
        "success_count": script.success_count,
        "fail_count": script.fail_count
    }


# ============================================================================
# WEBSOCKET
# ============================================================================

@app.websocket("/ws/status")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for live extraction status."""
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive
            data = await websocket.receive_text()
            # Echo back or handle commands
            await websocket.send_json({"type": "pong", "data": data})
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        manager.disconnect(websocket)


# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "DocFlow API"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
