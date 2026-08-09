"""Park-owned document library API."""
from __future__ import annotations

from pathlib import Path
import tempfile

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.core.permissions import require_any_role
from app.core.security import UserContext
from app.services.park_document_service import (
    ALLOWED_CATEGORIES,
    ALLOWED_SUFFIXES,
    delete_park_document,
    import_park_document,
    list_park_documents,
    search_park_documents,
)
from fastapi import Depends, Query


router = APIRouter()
MANAGE_ROLES = ("super_admin", "park_manager", "policy_manager", "investment_manager")
MAX_FILE_SIZE = 25 * 1024 * 1024


@router.get("/documents")
async def get_documents(
    _user: UserContext = Depends(require_any_role(*MANAGE_ROLES)),
):
    return {"success": True, "data": list_park_documents()}


@router.post("/documents", status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    category: str = Form(default="园区综合资料"),
    tags: str = Form(default=""),
    user: UserContext = Depends(require_any_role(*MANAGE_ROLES)),
):
    filename = Path(file.filename or "").name
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=415, detail="仅支持 PDF、DOCX、PPTX、TXT 和 Markdown 文件")
    normalized_category = category.strip() or "园区综合资料"
    if normalized_category not in ALLOWED_CATEGORIES:
        raise HTTPException(status_code=422, detail="资料分类无效")
    payload = await file.read(MAX_FILE_SIZE + 1)
    if len(payload) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="单个文件不能超过 25 MB")
    temporary = Path(tempfile.gettempdir()) / f"park-upload-{user.user_id}-{filename}"
    temporary.write_bytes(payload)
    try:
        record = await import_park_document(
            temporary,
            original_name=filename,
            category=normalized_category,
            tags=[item.strip() for item in tags.replace("，", ",").split(",") if item.strip()][:20],
            created_by=user.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    finally:
        temporary.unlink(missing_ok=True)
    return {"success": True, "data": record}


@router.delete("/documents/{document_id}")
async def remove_document(
    document_id: str,
    _user: UserContext = Depends(require_any_role(*MANAGE_ROLES)),
):
    if not delete_park_document(document_id):
        raise HTTPException(status_code=404, detail="资料不存在")
    return {"success": True}


@router.get("/documents/search")
async def search_documents(
    query: str = Query(min_length=2, max_length=300),
    limit: int = Query(default=10, ge=1, le=30),
    _user: UserContext = Depends(require_any_role(*MANAGE_ROLES)),
):
    return {"success": True, "data": search_park_documents(query, limit)}
