"""Import and export endpoints."""
import io
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select

from fourdpocket.api.deps import get_current_user, get_db
from fourdpocket.models.item import KnowledgeItem, ItemRead
from fourdpocket.models.tag import Tag, ItemTag
from fourdpocket.models.user import User
from fourdpocket.models.base import ItemType, SourcePlatform

router = APIRouter(tags=["import-export"])


MAX_IMPORT_SIZE = 10 * 1024 * 1024  # 10MB


@router.post("/import/{source}")
def import_bookmarks(
    source: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Import bookmarks from external sources."""
    raw = file.file.read(MAX_IMPORT_SIZE + 1)
    if len(raw) > MAX_IMPORT_SIZE:
        raise HTTPException(413, "Import file too large (max 10MB)")
    content = raw.decode("utf-8", errors="replace")
    imported = 0

    if source == "chrome":
        imported = _import_chrome_html(content, current_user.id, db)
    elif source == "pocket":
        imported = _import_pocket_html(content, current_user.id, db)
    elif source == "json":
        imported = _import_json(content, current_user.id, db)
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported source: {source}")

    return {"imported": imported, "source": source}


def _import_chrome_html(html: str, user_id, db: Session) -> int:
    """Parse Chrome bookmarks HTML and create items."""
    import re
    count = 0
    for match in re.finditer(r'<A HREF="([^"]+)"[^>]*>([^<]+)</A>', html, re.IGNORECASE):
        url, title = match.group(1), match.group(2).strip()
        if not url.startswith("http"):
            continue
        item = KnowledgeItem(
            user_id=user_id, url=url, title=title,
            item_type=ItemType.url, source_platform=SourcePlatform.generic,
        )
        db.add(item)
        count += 1
    db.commit()
    return count


def _import_pocket_html(html: str, user_id, db: Session) -> int:
    """Parse Pocket export HTML."""
    import re
    count = 0
    for match in re.finditer(r'<a href="([^"]+)"[^>]*>([^<]+)</a>', html, re.IGNORECASE):
        url, title = match.group(1), match.group(2).strip()
        if not url.startswith("http"):
            continue
        item = KnowledgeItem(
            user_id=user_id, url=url, title=title,
            item_type=ItemType.url, source_platform=SourcePlatform.generic,
        )
        db.add(item)
        count += 1
    db.commit()
    return count


def _import_json(json_str: str, user_id, db: Session) -> int:
    """Import from generic JSON array."""
    data = json.loads(json_str)
    items = data if isinstance(data, list) else data.get("items", [])
    if len(items) > 10000:
        raise HTTPException(413, "Too many items (max 10,000)")
    count = 0
    for entry in items:
        url = entry.get("url", "")
        title = entry.get("title", url)
        item = KnowledgeItem(
            user_id=user_id, url=url or None, title=title,
            description=entry.get("description"),
            content=entry.get("content"),
            item_type=ItemType.url, source_platform=SourcePlatform.generic,
        )
        db.add(item)
        count += 1
    db.commit()
    return count


@router.get("/export/{format}")
def export_bookmarks(
    format: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export bookmarks in various formats."""
    items = db.exec(
        select(KnowledgeItem).where(KnowledgeItem.user_id == current_user.id)
    ).all()

    if format == "json":
        data = [
            {
                "id": str(i.id), "url": i.url, "title": i.title,
                "description": i.description, "content": i.content,
                "source_platform": i.source_platform.value if i.source_platform else "generic",
                "item_type": i.item_type.value if i.item_type else "url",
                "is_favorite": i.is_favorite,
                "created_at": i.created_at.isoformat() if i.created_at else None,
            }
            for i in items
        ]
        content = json.dumps({"items": data, "exported_at": datetime.now(timezone.utc).isoformat()}, indent=2)
        return StreamingResponse(
            io.BytesIO(content.encode()), media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=4dpocket-export.json"},
        )

    elif format == "html":
        lines = [
            '<!DOCTYPE NETSCAPE-Bookmark-file-1>',
            '<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">',
            '<TITLE>4DPocket Bookmarks</TITLE>',
            '<H1>4DPocket Bookmarks</H1>',
            '<DL><p>',
        ]
        for i in items:
            if i.url:
                title = (i.title or i.url).replace("<", "&lt;").replace(">", "&gt;")
                lines.append(f'    <DT><A HREF="{i.url}">{title}</A>')
        lines.append('</DL><p>')
        content = "\n".join(lines)
        return StreamingResponse(
            io.BytesIO(content.encode()), media_type="text/html",
            headers={"Content-Disposition": "attachment; filename=4dpocket-bookmarks.html"},
        )

    elif format == "csv":
        import csv
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["title", "url", "description", "platform", "type", "favorite", "created_at"])
        for i in items:
            writer.writerow([
                i.title, i.url, i.description,
                i.source_platform.value if i.source_platform else "",
                i.item_type.value if i.item_type else "",
                i.is_favorite, i.created_at.isoformat() if i.created_at else "",
            ])
        content = output.getvalue()
        return StreamingResponse(
            io.BytesIO(content.encode()), media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=4dpocket-export.csv"},
        )

    elif format == "markdown":
        lines = ["# 4DPocket Export\n"]
        for i in items:
            title = i.title or "Untitled"
            if i.url:
                lines.append(f"- [{title}]({i.url})")
            else:
                lines.append(f"- {title}")
            if i.description:
                lines.append(f"  > {i.description[:200]}")
        content = "\n".join(lines)
        return StreamingResponse(
            io.BytesIO(content.encode()), media_type="text/markdown",
            headers={"Content-Disposition": "attachment; filename=4dpocket-export.md"},
        )

    else:
        raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")
