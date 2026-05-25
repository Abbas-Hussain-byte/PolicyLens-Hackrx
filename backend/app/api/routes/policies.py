"""Policy management routes — upload, list, delete, get summary."""

from fastapi import APIRouter, UploadFile, File, HTTPException
from app.core.parser import parse_pdf
from app.core.chunker import chunk_document
from app.core.embedder import embed_texts
from app.storage.faiss_store import faiss_store
from app.llm.gemini import generate_json
from app.llm.prompts import SUMMARY_PROMPT
from app.models.schemas import PolicyUploadResponse, PolicyListResponse, PolicyInfo
from app.config import settings
import uuid
import shutil
import json
from pathlib import Path
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/policies", tags=["policies"])

# Simple metadata store (JSON file-based for MVP)
METADATA_FILE = Path(settings.data_dir) / "policies_meta.json"


def _load_metadata() -> dict:
    if METADATA_FILE.exists():
        with open(METADATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_metadata(data: dict):
    METADATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(METADATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


@router.post("/upload", response_model=PolicyUploadResponse)
async def upload_policy(file: UploadFile = File(...)):
    """Upload an insurance policy PDF and process it.

    Pipeline: Upload → Parse → Chunk → Embed → Index → Summarize
    """
    # Validate file
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    if file.size and file.size > settings.max_upload_size_mb * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"File too large (max {settings.max_upload_size_mb}MB)")

    policy_id = str(uuid.uuid4())[:12]

    # Save file
    upload_path = Path(settings.upload_dir) / f"{policy_id}.pdf"
    upload_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(upload_path, "wb") as f:
            content = await file.read()
            f.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")

    # Parse PDF
    try:
        document = parse_pdf(upload_path)
    except Exception as e:
        upload_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"Failed to parse PDF: {e}")

    if document.is_scanned:
        upload_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=400,
            detail="This appears to be a scanned PDF with little extractable text. "
                   "Please upload a text-based PDF. OCR support coming soon.",
        )

    if document.total_chars < 100:
        upload_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="PDF contains too little text to analyze.")

    # Chunk
    chunks = chunk_document(document, policy_id=policy_id)
    if not chunks:
        upload_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Could not extract meaningful content from PDF.")

    # Embed
    texts = [c.text for c in chunks]
    embeddings = embed_texts(texts)

    # Index in FAISS
    faiss_store.add_policy(policy_id, embeddings, chunks)

    # Generate summary (async, but we wait for it since it's part of the upload response)
    summary = ""
    try:
        # Use first ~3000 chars for summary
        summary_text = document.full_text[:3000]
        prompt = SUMMARY_PROMPT.format(text=summary_text)
        result = await generate_json(prompt, temperature=0.3)
        summary = result.get("one_line_summary", "")

        # Store full summary
        summary_data = result
    except Exception as e:
        logger.warning(f"Summary generation failed: {e}")
        summary_data = {}

    # Save metadata
    meta = _load_metadata()
    meta[policy_id] = {
        "policy_id": policy_id,
        "filename": file.filename,
        "page_count": document.total_pages,
        "chunk_count": len(chunks),
        "uploaded_at": datetime.now().isoformat(),
        "summary": summary,
        "summary_data": summary_data,
        "total_chars": document.total_chars,
    }
    _save_metadata(meta)

    logger.info(f"Policy uploaded: {policy_id} ({file.filename}, {len(chunks)} chunks)")

    return PolicyUploadResponse(
        policy_id=policy_id,
        filename=file.filename,
        page_count=document.total_pages,
        chunk_count=len(chunks),
        summary=summary,
    )


@router.get("/", response_model=PolicyListResponse)
async def list_policies():
    """List all uploaded policies."""
    meta = _load_metadata()
    policies = [
        PolicyInfo(
            policy_id=v["policy_id"],
            filename=v["filename"],
            page_count=v["page_count"],
            chunk_count=v["chunk_count"],
            uploaded_at=v["uploaded_at"],
            summary=v.get("summary", ""),
        )
        for v in meta.values()
    ]
    return PolicyListResponse(policies=policies, total=len(policies))


@router.get("/{policy_id}")
async def get_policy(policy_id: str):
    """Get details of a specific policy."""
    meta = _load_metadata()
    if policy_id not in meta:
        raise HTTPException(status_code=404, detail="Policy not found")

    policy_data = meta[policy_id]
    return {
        **policy_data,
        "has_index": faiss_store.has_policy(policy_id),
    }


@router.delete("/{policy_id}")
async def delete_policy(policy_id: str):
    """Delete a policy and its index."""
    meta = _load_metadata()
    if policy_id not in meta:
        raise HTTPException(status_code=404, detail="Policy not found")

    # Delete FAISS index
    faiss_store.delete_policy(policy_id)

    # Delete uploaded file
    upload_path = Path(settings.upload_dir) / f"{policy_id}.pdf"
    upload_path.unlink(missing_ok=True)

    # Remove metadata
    del meta[policy_id]
    _save_metadata(meta)

    return {"status": "deleted", "policy_id": policy_id}
