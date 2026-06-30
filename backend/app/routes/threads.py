from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import Message, Thread

router = APIRouter(prefix="/api/threads", tags=["threads"])


class ThreadUpdateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    status: Literal["regular", "archived"] | None = None


@router.get("")
def list_threads(
    tenant_id: str = Query(min_length=1),
    workspace_id: str = Query(min_length=1),
    user_id: str = Query(min_length=1),
    limit: int = 20,
    session: Session = Depends(get_session),
) -> dict[str, list[dict[str, object]]]:
    bounded_limit = max(1, min(limit, 50))
    rows = session.execute(
        select(
            Thread.thread_id,
            Thread.title,
            Thread.workspace_id,
            Thread.status,
            func.count(Message.message_id).label("message_count"),
            func.max(Message.created_at).label("last_message_at"),
        )
        .outerjoin(Message, Message.thread_id == Thread.thread_id)
        .where(
            Thread.tenant_id == tenant_id,
            Thread.workspace_id == workspace_id,
            Thread.user_id == user_id,
            Thread.status.in_(("regular", "archived")),
        )
        .group_by(Thread.thread_id, Thread.title, Thread.workspace_id, Thread.status)
        .order_by(func.max(Message.created_at).desc().nulls_last(), Thread.thread_id.desc())
        .limit(bounded_limit)
    ).all()

    threads: list[dict[str, object]] = []
    for row in rows:
        last_message = session.scalars(
            select(Message)
            .where(
                Message.thread_id == row.thread_id,
                Message.tenant_id == tenant_id,
                Message.workspace_id == workspace_id,
            )
            .order_by(Message.created_at.desc(), Message.message_id.desc())
            .limit(1)
        ).first()
        threads.append(
            {
                "thread_id": row.thread_id,
                "title": row.title,
                "workspace_id": row.workspace_id,
                "status": row.status or "regular",
                "last_message": last_message.content if last_message is not None else "",
                "last_message_at": row.last_message_at.isoformat() if row.last_message_at else None,
                "message_count": row.message_count,
            }
        )

    return {"threads": threads}


@router.get("/{thread_id}")
def get_thread(
    thread_id: str,
    tenant_id: str = Query(min_length=1),
    workspace_id: str = Query(min_length=1),
    user_id: str = Query(min_length=1),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    thread = session.scalar(
        select(Thread).where(
            Thread.thread_id == thread_id,
            Thread.tenant_id == tenant_id,
            Thread.workspace_id == workspace_id,
            Thread.user_id == user_id,
        )
    )
    if thread is None:
        raise HTTPException(status_code=404, detail="thread_not_found")

    messages = session.scalars(
        select(Message)
        .where(
            Message.thread_id == thread_id,
            Message.tenant_id == tenant_id,
            Message.workspace_id == workspace_id,
        )
        .order_by(Message.created_at.asc(), Message.message_id.asc())
    ).all()

    return {
        "thread": {
            "thread_id": thread.thread_id,
            "title": thread.title,
            "workspace_id": thread.workspace_id,
            "status": thread.status or "regular",
            "created_at": thread.created_at.isoformat() if thread.created_at else None,
        },
        "messages": [
            {
                "message_id": message.message_id,
                "role": message.role,
                "content": message.content,
                "run_id": message.run_id,
                "created_at": message.created_at.isoformat() if message.created_at else None,
            }
            for message in messages
        ],
    }


@router.patch("/{thread_id}")
def update_thread(
    thread_id: str,
    request: ThreadUpdateRequest,
    tenant_id: str = Query(min_length=1),
    workspace_id: str = Query(min_length=1),
    user_id: str = Query(min_length=1),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    thread = session.scalar(
        select(Thread).where(
            Thread.thread_id == thread_id,
            Thread.tenant_id == tenant_id,
            Thread.workspace_id == workspace_id,
            Thread.user_id == user_id,
        )
    )
    if thread is None:
        raise HTTPException(status_code=404, detail="thread_not_found")

    if request.title is not None:
        stripped_title = request.title.strip()
        thread.title = stripped_title[:200] if stripped_title else thread.title
    if request.status is not None:
        thread.status = request.status

    session.add(thread)
    session.commit()
    session.refresh(thread)

    return {
        "thread_id": thread.thread_id,
        "title": thread.title,
        "workspace_id": thread.workspace_id,
        "status": thread.status or "regular",
    }


@router.delete("/{thread_id}")
def delete_thread(
    thread_id: str,
    tenant_id: str = Query(min_length=1),
    workspace_id: str = Query(min_length=1),
    user_id: str = Query(min_length=1),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    thread = session.scalar(
        select(Thread).where(
            Thread.thread_id == thread_id,
            Thread.tenant_id == tenant_id,
            Thread.workspace_id == workspace_id,
            Thread.user_id == user_id,
        )
    )
    if thread is None:
        raise HTTPException(status_code=404, detail="thread_not_found")

    session.execute(
        delete(Message).where(
            Message.thread_id == thread_id,
            Message.tenant_id == tenant_id,
            Message.workspace_id == workspace_id,
        )
    )
    session.delete(thread)
    session.commit()

    return {"thread_id": thread_id, "deleted": True}
