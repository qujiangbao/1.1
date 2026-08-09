"""Park-owned document library API."""
from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.core.permissions import require_any_role
from app.core.security import UserContext
from app.services.park_document_service import (
    ALLOWED_CATEGORIES,
    ALLOWED_SUFFIXES,
    delete_park_document,
    import_park_document,
    list_park_documents,
    preview_park_document,
    restore_park_document,
    search_park_documents,
)
from fastapi import Depends, Query


router = APIRouter()
MANAGE_ROLES = ("super_admin", "park_manager", "policy_manager", "investment_manager")
MAX_FILE_SIZE = 25 * 1024 * 1024


@router.get("/documents")
async def get_documents(
    include_archived: bool = Query(default=False),
    _user: UserContext = Depends(require_any_role(*MANAGE_ROLES)),
):
    return {"success": True, "data": list_park_documents(include_archived=include_archived)}


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
        raise HTTPException(status_code=415, detail="仅支持 PDF、DOCX、PPTX、XLSX、CSV、TXT 和 Markdown 文件")
    normalized_category = category.strip() or "园区综合资料"
    if normalized_category not in ALLOWED_CATEGORIES:
        raise HTTPException(status_code=422, detail="资料分类无效")
    temporary: Path | None = None
    try:
        total = 0
        with NamedTemporaryFile(
            prefix="park-upload-",
            suffix=suffix,
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=413,
                        detail="单个文件不能超过 25 MB",
                    )
                handle.write(chunk)
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
        await file.close()
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return {"success": True, "data": record}


@router.post("/documents/preview")
async def preview_document(
    file: UploadFile = File(...),
    category: str = Form(default="园区综合资料"),
    _user: UserContext = Depends(require_any_role(*MANAGE_ROLES)),
):
    filename = Path(file.filename or "").name
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=415, detail="仅支持 PDF、DOCX、PPTX、XLSX、CSV、TXT 和 Markdown 文件")
    normalized_category = category.strip() or "园区综合资料"
    if normalized_category not in ALLOWED_CATEGORIES:
        raise HTTPException(status_code=422, detail="资料分类无效")
    temporary: Path | None = None
    try:
        total = 0
        with NamedTemporaryFile(prefix="park-preview-", suffix=suffix, delete=False) as handle:
            temporary = Path(handle.name)
            while chunk := await file.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_FILE_SIZE:
                    raise HTTPException(status_code=413, detail="单个文件不能超过 25 MB")
                handle.write(chunk)
        data = await preview_park_document(
            temporary,
            original_name=filename,
            category=normalized_category,
        )
    except ValueError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    finally:
        await file.close()
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return {"success": True, "data": data}


@router.delete("/documents/{document_id}")
async def remove_document(
    document_id: str,
    user: UserContext = Depends(require_any_role(*MANAGE_ROLES)),
):
    if not delete_park_document(document_id, archived_by=user.user_id):
        raise HTTPException(status_code=404, detail="资料不存在")
    return {"success": True, "recoverable": True}


@router.post("/documents/{document_id}/restore")
async def restore_document(
    document_id: str,
    user: UserContext = Depends(require_any_role(*MANAGE_ROLES)),
):
    if not restore_park_document(document_id, restored_by=user.user_id):
        raise HTTPException(status_code=404, detail="未找到已归档资料")
    return {"success": True}


@router.get("/documents/search")
async def search_documents(
    query: str = Query(min_length=2, max_length=300),
    limit: int = Query(default=10, ge=1, le=30),
    _user: UserContext = Depends(require_any_role(*MANAGE_ROLES)),
):
    return {"success": True, "data": search_park_documents(query, limit)}
