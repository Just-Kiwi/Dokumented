"""
FastAPI application for Dokumented.
Main entry point with all routes and WebSocket support.
"""
import logging
import json
from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, WebSocket, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import update as sql_update
from db.database import get_db, init_db
from db.models import ExtractionResult, ScriptLibrary, BatchQueue, StatusEnum, BatchStatusEnum
from models.schemas import (
    SchemaRequest, ExtractRequest,
    HumanOverridesRequest, ExtractionReportResponse, WSEvent,
    CreditCheckResponse, CreditCheckStatus,
    BatchStartRequest, BatchResponse, BatchFileStatus
)
from services.pipeline import ExtractionPipeline, PipelineError
from parsers.doc_parser import DocumentParser
from config import (
    UPLOAD_FOLDER, OPENROUTER_API_KEY, OPENROUTER_BASE_URL,
    MAX_RETRIES, CONFIDENCE_THRESHOLD, get_config, mask_api_key,
    MAX_BATCH_SIZE, BATCH_DOWNLOAD_MODE
)
from exceptions import AnthropicCreditError, MercuryCreditError, APIError, APITimeoutError, APIAuthenticationError
from openai import OpenAI
from openai import APIError as OpenAIAPIError
import os
import asyncio
from datetime import datetime
from typing import Dict, List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

init_db()

app = FastAPI(title="Dokumented", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected, total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected, remaining connections: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"Broadcast error: {e}")


manager = ConnectionManager()

current_events_queue = []


def emit_event(event: dict):
    """Add event to queue for WebSocket broadcasting."""
    current_events_queue.append(event)
    asyncio.create_task(manager.broadcast(event))


@app.get("/api/config")
def list_config():
    """List all configuration values from .env file. API keys are masked."""
    return get_config()


@app.get("/api/config/{key}")
def get_config_by_key(key: str):
    """Get a specific configuration value from .env file."""
    config = get_config()
    if key not in config:
        raise HTTPException(status_code=404, detail=f"Config '{key}' not found")
    return config[key]


@app.get("/api/credits", response_model=CreditCheckResponse)
def check_credits():
    """Check if API keys are configured and have valid credits."""
    
    def check_anthropic():
        api_key = OPENROUTER_API_KEY
        base_url = OPENROUTER_BASE_URL
        
        if not api_key:
            return CreditCheckStatus(
                provider="OpenRouter (Claude)",
                configured=False,
                has_credits=False,
                error="API key not configured. Set OPENROUTER_API_KEY in .env file."
            )
        
        try:
            client = OpenAI(api_key=api_key, base_url=base_url)
            client.chat.completions.create(
                model="anthropic/claude-3.5-sonnet",
                max_tokens=10,
                messages=[{"role": "user", "content": "hi"}]
            )
            return CreditCheckStatus(provider="OpenRouter (Claude)", configured=True, has_credits=True)
        except OpenAIAPIError as e:
            error_str = str(e).lower()
            if "credit" in error_str or "quota" in error_str or "insufficient" in error_str or "billing" in error_str:
                return CreditCheckStatus(
                    provider="OpenRouter (Claude)", configured=True, has_credits=False,
                    error="Insufficient credits. Add credits to continue."
                )
            return CreditCheckStatus(provider="OpenRouter (Claude)", configured=True, has_credits=False, error=str(e))
        except Exception as e:
            return CreditCheckStatus(provider="OpenRouter (Claude)", configured=True, has_credits=False, error=str(e))
    
    def check_mercury():
        api_key = OPENROUTER_API_KEY
        base_url = OPENROUTER_BASE_URL
        
        if not api_key:
            return CreditCheckStatus(
                provider="OpenRouter (Mercury)",
                configured=False,
                has_credits=False,
                error="API key not configured. Set OPENROUTER_API_KEY in .env file."
            )
        
        try:
            client = OpenAI(api_key=api_key, base_url=base_url)
            client.chat.completions.create(
                model="inception/mercury-2",
                max_tokens=10,
                messages=[{"role": "user", "content": "hello"}]
            )
            return CreditCheckStatus(provider="OpenRouter (Mercury)", configured=True, has_credits=True)
        except OpenAIAPIError as e:
            error_str = str(e).lower()
            if "credit" in error_str or "quota" in error_str or "insufficient" in error_str or "billing" in error_str:
                return CreditCheckStatus(
                    provider="OpenRouter (Mercury)", configured=True, has_credits=False,
                    error="Insufficient credits. Add credits to continue."
                )
            return CreditCheckStatus(provider="OpenRouter (Mercury)", configured=True, has_credits=False, error=str(e))
        except Exception as e:
            return CreditCheckStatus(provider="OpenRouter (Mercury)", configured=True, has_credits=False, error=str(e))
    
    return CreditCheckResponse(anthropic=check_anthropic(), mercury=check_mercury())


@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Upload a document and return raw text."""
    logger.info(f"Uploading file: {file.filename}")
    
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    
    try:
        content = await file.read()
        with open(file_path, 'wb') as f:
            f.write(content)
    except Exception as e:
        logger.error(f"Failed to save uploaded file: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to save file: {str(e)}")
    
    try:
        raw_text = DocumentParser.parse(file_path)
        logger.info(f"File parsed successfully, {len(raw_text)} chars")
    except Exception as e:
        logger.error(f"Failed to parse document: {e}")
        raise HTTPException(status_code=400, detail=f"Parse error: {str(e)}")
    
    return {
        "filename": file.filename,
        "raw_text": raw_text[:10000],
        "full_text_length": len(raw_text)
    }


@app.post("/api/extract")
async def extract(request: ExtractRequest, db: Session = Depends(get_db)):
    """Extract fields from a document."""
    logger.info(f"Starting extraction for: {request.filename}")
    
    llm_key = OPENROUTER_API_KEY
    dllm_key = OPENROUTER_API_KEY
    dllm_url = OPENROUTER_BASE_URL
    
    if not llm_key:
        logger.error("OPENROUTER_API_KEY not configured")
        raise HTTPException(status_code=400, detail="OPENROUTER_API_KEY not configured. Set it in .env file.")
    
    if not request.filename:
        raise HTTPException(status_code=400, detail="Filename is required")
    
    if not request.raw_text:
        raise HTTPException(status_code=400, detail="raw_text is required")
    
    pipeline = ExtractionPipeline(
        db,
        llm_api_key=llm_key,
        dllm_api_key=dllm_key,
        dllm_base_url=dllm_url
    )
    
    current_events_queue.clear()
    
    try:
        result_id = await pipeline.extract(
            request.filename,
            request.raw_text,
            request.field_definitions or [],
            events_callback=emit_event
        )
        logger.info(f"Extraction completed successfully, result_id: {result_id}")
        return {"result_id": result_id, "status": "success"}
        
    except AnthropicCreditError as e:
        logger.error(f"Anthropic credit error: {e.message}")
        raise HTTPException(
            status_code=402,
            detail={
                "error": "Anthropic API (Claude) has insufficient credits",
                "message": e.message,
                "provider": e.provider,
                "suggestion": "Add credits to continue"
            }
        )
    except MercuryCreditError as e:
        logger.error(f"Mercury credit error: {e.message}")
        raise HTTPException(
            status_code=402,
            detail={
                "error": "Mercury/Inception Labs API has insufficient credits",
                "message": e.message,
                "provider": e.provider,
                "suggestion": "Add credits to continue"
            }
        )
    except APIError as e:
        logger.error(f"API error from {e.provider}: {e.message}")
        raise HTTPException(
            status_code=502,
            detail={
                "error": f"{e.provider} API error",
                "message": e.message,
                "provider": e.provider,
                "error_code": e.error_code,
                "suggestion": "Check API configuration and try again"
            }
        )
    except PipelineError as e:
        logger.error(f"Pipeline error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected extraction error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Extraction error: {str(e)}")


@app.get("/api/extraction/{result_id}", response_model=ExtractionReportResponse)
def get_extraction(result_id: int, db: Session = Depends(get_db)):
    """Get an extraction result."""
    result = db.query(ExtractionResult).filter_by(id=result_id).first()
    if not result:
        raise HTTPException(status_code=404, detail=f"Result {result_id} not found")
    
    dllm_report = result.dllm_report or {}
    dllm_fields = dllm_report.get("fields", {})
    
    missing_fields = [
        field_name for field_name, field_data in dllm_fields.items()
        if field_data.get("status") in ["missing", "uncertain"]
    ]
    
    schema = [
        {"name": field_name, "status": field_data.get("status"), "confidence": field_data.get("confidence")}
        for field_name, field_data in dllm_fields.items()
    ]
    
    return ExtractionReportResponse(
        result_id=result.id,
        filename=result.filename,
        script_id=result.script_id,
        script_version=result.script_version,
        status=result.status.value,
        extracted_json=result.extracted_json,
        missing_fields=missing_fields,
        schema=schema,
        dllm_report=result.dllm_report or {}
    )


@app.get("/api/extraction/{result_id}/validation-log")
def get_validation_log(result_id: int, db: Session = Depends(get_db)):
    """Get the dLLM validation log for an extraction result."""
    result = db.query(ExtractionResult).filter_by(id=result_id).first()
    if not result:
        raise HTTPException(status_code=404, detail=f"Result {result_id} not found")
    
    dllm_report = result.dllm_report or {}
    fields = dllm_report.get("fields", {})
    
    if not fields:
        return {
            "result_id": result_id,
            "message": "No dLLM validation data available",
            "fields": []
        }
    
    validation_log = []
    for field_name, field_data in fields.items():
        validation_log.append({
            "field": field_name,
            "status": field_data.get("status", "unknown"),
            "value": field_data.get("value"),
            "confidence": field_data.get("confidence", 0.0)
        })
    
    return {
        "result_id": result_id,
        "filename": result.filename,
        "script_id": result.script_id,
        "script_version": result.script_version,
        "total_fields": len(validation_log),
        "filled": len([v for v in validation_log if v["status"] == "filled"]),
        "missing": len([v for v in validation_log if v["status"] == "missing"]),
        "uncertain": len([v for v in validation_log if v["status"] == "uncertain"]),
        "fields": validation_log
    }


@app.post("/api/extraction/{result_id}/overrides")
def apply_overrides(result_id: int, request: HumanOverridesRequest, db: Session = Depends(get_db)):
    """Apply human overrides to missing/uncertain fields."""
    result = db.query(ExtractionResult).filter_by(id=result_id).first()
    if not result:
        raise HTTPException(status_code=404, detail=f"Result {result_id} not found")
    
    pipeline = ExtractionPipeline(db)
    overrides_dict = {o.field_name: o.value for o in request.overrides}
    
    try:
        final_json = pipeline.apply_human_overrides(result_id, overrides_dict)
        logger.info(f"Applied {len(overrides_dict)} overrides to result {result_id}")
        return {"result_id": result_id, "extracted_json": final_json, "status": "complete"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to apply overrides: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/scripts")
def list_scripts(db: Session = Depends(get_db)):
    """List all scripts in the library."""
    scripts = db.query(ScriptLibrary).all()
    return [
        {
            "id": s.id,
            "version": s.version,
            "success_count": s.success_count,
            "fail_count": s.fail_count,
            "created_at": s.created_at,
            "updated_at": s.updated_at
        }
        for s in scripts
    ]


@app.get("/api/scripts/{script_id}")
def get_script(script_id: int, db: Session = Depends(get_db)):
    """Get a script by ID."""
    script = db.query(ScriptLibrary).filter_by(id=script_id).first()
    if not script:
        raise HTTPException(status_code=404, detail=f"Script {script_id} not found")
    
    return {
        "id": script.id,
        "script_body": script.script_body,
        "version": script.version,
        "success_count": script.success_count,
        "fail_count": script.fail_count
    }


@app.delete("/api/scripts")
def delete_all_scripts(db: Session = Depends(get_db)):
    """Delete all scripts from the script library."""
    count = db.query(ScriptLibrary).delete()
    db.commit()
    return {"status": "deleted", "count": count}


# Batch processing endpoints
@app.post("/api/batch/start")
async def start_batch(request: BatchStartRequest, db: Session = Depends(get_db)):
    """Start a batch extraction process."""
    if len(request.files) > MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum batch size is {MAX_BATCH_SIZE} files"
        )
    
    files_data = [
        {
            "filename": f.filename,
            "raw_text": f.raw_text,
            "status": "unprocessed",
            "result_id": None,
            "error": None
        }
        for f in request.files
    ]
    
    schema_data = [f.model_dump() for f in (request.field_definitions or [])]
    
    batch = BatchQueue(
        status=BatchStatusEnum.pending,
        files=files_data,
        schema=schema_data
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)
    
    return {"batch_id": batch.id, "status": "pending", "total_files": len(files_data)}


@app.get("/api/batch/{batch_id}")
def get_batch(batch_id: int, db: Session = Depends(get_db)):
    """Get batch status and results."""
    batch = db.query(BatchQueue).filter_by(id=batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail=f"Batch {batch_id} not found")
    
    db.refresh(batch)
    logger.info(f"[DEBUG get_batch] batch_id={batch_id}, files count={len(batch.files)}")
    for i, f in enumerate(batch.files):
        logger.info(f"[DEBUG get_batch] file[{i}]={f.get('filename')}, status={f.get('status')}, result_id={f.get('result_id')}")
    
    processed_count = sum(1 for f in batch.files if f.get("status") == "processed")
    logger.info(f"[DEBUG get_batch] processed_count={processed_count}")
    
    return {
        "batch_id": batch.id,
        "status": batch.status.value,
        "current_index": batch.current_index,
        "files": batch.files,
        "total_files": len(batch.files),
        "processed_count": processed_count,
        "created_at": batch.created_at,
        "updated_at": batch.updated_at
    }


@app.post("/api/batch/{batch_id}/pause")
def pause_batch(batch_id: int, db: Session = Depends(get_db)):
    """Pause a batch processing."""
    batch = db.query(BatchQueue).filter_by(id=batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail=f"Batch {batch_id} not found")
    
    if batch.status != BatchStatusEnum.processing:
        raise HTTPException(status_code=400, detail="Batch is not currently processing")
    
    batch.status = BatchStatusEnum.paused
    
    if batch.current_index < len(batch.files):
        batch.files[batch.current_index]["status"] = "paused"
    
    db.commit()
    
    return {"batch_id": batch.id, "status": batch.status.value}


@app.post("/api/batch/{batch_id}/resume")
def resume_batch(batch_id: int, db: Session = Depends(get_db)):
    """Resume a paused batch."""
    batch = db.query(BatchQueue).filter_by(id=batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail=f"Batch {batch_id} not found")
    
    if batch.status != BatchStatusEnum.paused:
        raise HTTPException(status_code=400, detail="Batch is not paused")
    
    batch.status = BatchStatusEnum.processing
    
    if batch.current_index < len(batch.files):
        batch.files[batch.current_index]["status"] = "processing"
    
    db.commit()
    
    return {"batch_id": batch.id, "status": batch.status.value}


@app.post("/api/batch/{batch_id}/cancel")
def cancel_batch(batch_id: int, db: Session = Depends(get_db)):
    """Cancel a batch processing."""
    batch = db.query(BatchQueue).filter_by(id=batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail=f"Batch {batch_id} not found")
    
    batch.status = BatchStatusEnum.cancelled
    
    for i in range(batch.current_index, len(batch.files)):
        batch.files[i]["status"] = "cancelled"
    
    db.commit()
    
    return {"batch_id": batch.id, "status": batch.status.value}


@app.post("/api/batch/{batch_id}/clear")
def clear_batch(batch_id: int, db: Session = Depends(get_db)):
    """Clear a batch from database."""
    batch = db.query(BatchQueue).filter_by(id=batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail=f"Batch {batch_id} not found")
    
    db.delete(batch)
    db.commit()
    
    return {"status": "cleared"}


@app.post("/api/batch/{batch_id}/process")
async def process_batch(batch_id: int, db: Session = Depends(get_db)):
    """Process a batch (runs the extraction for all files)."""
    logger.info(f">>> process_batch called for batch_id={batch_id}")
    batch = db.query(BatchQueue).filter_by(id=batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail=f"Batch {batch_id} not found")
    
    logger.info(f">>> batch.schema = {batch.schema}")
    
    if batch.status == BatchStatusEnum.completed:
        logger.info(">> Batch already completed, resetting to pending for re-extraction")
        batch.status = BatchStatusEnum.pending
        batch.current_index = 0
        for f in batch.files:
            f["status"] = "unprocessed"
            f["result_id"] = None
            f["error"] = None
        db.commit()
    
    llm_key = OPENROUTER_API_KEY
    dllm_key = OPENROUTER_API_KEY
    dllm_url = OPENROUTER_BASE_URL
    
    if not llm_key:
        raise HTTPException(status_code=400, detail="OPENROUTER_API_KEY not configured")
    
    pipeline = ExtractionPipeline(
        db,
        llm_api_key=llm_key,
        dllm_api_key=dllm_key,
        dllm_base_url=dllm_url
    )
    
    schema = batch.schema or []
    logger.info(f">>> Using schema: {schema}")
    batch.status = BatchStatusEnum.processing
    db.commit()
    
    while batch.current_index < len(batch.files):
        if batch.status == BatchStatusEnum.cancelled:
            break
        
        while batch.status == BatchStatusEnum.paused:
            await asyncio.sleep(1)
            db.refresh(batch)
            if batch.status == BatchStatusEnum.cancelled:
                break
        
        if batch.status == BatchStatusEnum.cancelled:
            break
        
        file_data = batch.files[batch.current_index]
        file_data["status"] = "processing"
        db.commit()
        
        try:
            result_id = await pipeline.extract(
                file_data["filename"],
                file_data["raw_text"],
                schema,
                events_callback=emit_event
            )
            
            files = list(batch.files)  # Create a new copy
            files[batch.current_index]["status"] = "processed"
            files[batch.current_index]["result_id"] = result_id
            files[batch.current_index]["error"] = None
            batch.files = files
            logger.info(f">> File processed: {file_data['filename']}, result_id={result_id}")
            db.execute(
                sql_update(BatchQueue)
                .where(BatchQueue.id == batch_id)
                .values(files=batch.files)
            )
            db.commit()
            db.refresh(batch)
            
        except Exception as e:
            logger.error(f">> File failed: {file_data['filename']}: {e}")
            files = list(batch.files)
            files[batch.current_index]["status"] = "cancelled"
            files[batch.current_index]["error"] = str(e)
            batch.files = files
            db.execute(
                sql_update(BatchQueue)
                .where(BatchQueue.id == batch_id)
                .values(files=batch.files)
            )
            db.commit()
        
        batch.current_index += 1
        db.commit()
    
    if batch.status != BatchStatusEnum.cancelled:
        batch.status = BatchStatusEnum.completed
    
    db.commit()
    
    return {
        "batch_id": batch.id,
        "status": batch.status.value,
        "processed_count": sum(1 for f in batch.files if f.get("status") == "processed")
    }
    """Download batch results as JSON."""
    batch = db.query(BatchQueue).filter_by(id=batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail=f"Batch {batch_id} not found")
    
    if BATCH_DOWNLOAD_MODE == "single":
        results = []
        for f in batch.files:
            if f.get("status") == "processed" and f.get("result_id"):
                result = db.query(ExtractionResult).filter_by(id=f["result_id"]).first()
                if result:
                    results.append({
                        "filename": f["filename"],
                        "extracted_json": result.extracted_json,
                        "status": result.status.value
                    })
        return {"files": results}
    else:
        combined = {}
        for f in batch.files:
            if f.get("status") == "processed" and f.get("result_id"):
                result = db.query(ExtractionResult).filter_by(id=f["result_id"]).first()
                if result:
                    combined[f["filename"]] = result.extracted_json
        return combined


@app.get("/api/batch")
def list_batches(db: Session = Depends(get_db)):
    """List all batches."""
    batches = db.query(BatchQueue).order_by(BatchQueue.created_at.desc()).all()
    return [
        {
            "batch_id": b.id,
            "status": b.status.value,
            "current_index": b.current_index,
            "total_files": len(b.files),
            "processed_count": sum(1 for f in b.files if f.get("status") == "processed"),
            "created_at": b.created_at,
            "updated_at": b.updated_at
        }
        for b in batches
    ]


@app.post("/api/batch/{batch_id}/process")
async def process_batch(batch_id: int, db: Session = Depends(get_db)):
    """Process a batch (runs the extraction for all files)."""
    logger.info(f">>> PROCESS BATCH START batch_id={batch_id}")
    batch = db.query(BatchQueue).filter_by(id=batch_id).first()
    if not batch:
        raise HTTPException(status_code=404, detail=f"Batch {batch_id} not found")
    
    logger.info(f">>> BATCH SCHEMA = {batch.schema}")
    logger.info(f">>> BATCH STATUS = {batch.status}")
    
    if batch.status == BatchStatusEnum.completed:
        raise HTTPException(status_code=400, detail="Batch already completed")
    
    llm_key = OPENROUTER_API_KEY
    dllm_key = OPENROUTER_API_KEY
    dllm_url = OPENROUTER_BASE_URL
    
    if not llm_key:
        raise HTTPException(status_code=400, detail="OPENROUTER_API_KEY not configured")
    
    pipeline = ExtractionPipeline(
        db,
        llm_api_key=llm_key,
        dllm_api_key=dllm_key,
        dllm_base_url=dllm_url
    )
    
    schema = batch.schema or []
    logger.info(f">>> SCHEMA TO USE = {schema}")
    batch.status = BatchStatusEnum.processing
    db.commit()
    
    while batch.current_index < len(batch.files):
        if batch.status == BatchStatusEnum.cancelled:
            break
        
        while batch.status == BatchStatusEnum.paused:
            await asyncio.sleep(1)
            db.refresh(batch)
            if batch.status == BatchStatusEnum.cancelled:
                break
        
        if batch.status == BatchStatusEnum.cancelled:
            break
        
        file_data = batch.files[batch.current_index]
        file_data["status"] = "processing"
        db.commit()
        
        try:
            result_id = await pipeline.extract(
                file_data["filename"],
                file_data["raw_text"],
                schema,
                events_callback=emit_event
            )
            
            files = list(batch.files)  # Create a new copy
            files[batch.current_index]["status"] = "processed"
            files[batch.current_index]["result_id"] = result_id
            files[batch.current_index]["error"] = None
            batch.files = files
            logger.info(f">> File processed: {file_data['filename']}, result_id={result_id}")
            db.execute(
                sql_update(BatchQueue)
                .where(BatchQueue.id == batch_id)
                .values(files=batch.files)
            )
            db.commit()
            db.refresh(batch)
            
        except Exception as e:
            logger.error(f">> File failed: {file_data['filename']}: {e}")
            files = list(batch.files)
            files[batch.current_index]["status"] = "cancelled"
            files[batch.current_index]["error"] = str(e)
            batch.files = files
            db.execute(
                sql_update(BatchQueue)
                .where(BatchQueue.id == batch_id)
                .values(files=batch.files)
            )
            db.commit()
        
        batch.current_index += 1
        db.commit()
    
    if batch.status != BatchStatusEnum.cancelled:
        batch.status = BatchStatusEnum.completed
    
    db.commit()
    
    return {
        "batch_id": batch.id,
        "status": batch.status.value,
        "processed_count": sum(1 for f in batch.files if f.get("status") == "processed")
    }


@app.websocket("/ws/status")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for live extraction status."""
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_json({"type": "pong", "data": data})
    except Exception as e:
        logger.warning(f"WebSocket error: {e}")
    finally:
        manager.disconnect(websocket)


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "Dokumented API"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
