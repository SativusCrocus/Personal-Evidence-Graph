from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from ..config import Settings
from ..deps import settings_dep
from ..models.schemas import AnswerResponse, QueryRequest
from ..security import limiter
from ..security.sanitize import sanitize_question
from ..services import answer as answer_svc

log = logging.getLogger("evg.router.query")
router = APIRouter(tags=["query"])


@router.post("/query", response_model=AnswerResponse)
@limiter.limit("30/minute")
async def query(
    request: Request,
    body: QueryRequest,
    s: Settings = Depends(settings_dep),
) -> AnswerResponse:
    q = sanitize_question(body.question)
    if not q:
        raise HTTPException(status_code=400, detail="empty question")
    return await answer_svc.answer_with_proof(
        q,
        k=body.k,
        source_types=body.source_types,
        date_from=body.date_from,
        date_to=body.date_to,
        settings=s,
    )


@router.post("/query/stream")
@limiter.limit("30/minute")
async def query_stream(
    request: Request,
    body: QueryRequest,
    s: Settings = Depends(settings_dep),
):
    q = sanitize_question(body.question)
    if not q:
        raise HTTPException(status_code=400, detail="empty question")

    async def gen():
        async for ev in answer_svc.stream_answer(
            q,
            k=body.k,
            source_types=body.source_types,
            date_from=body.date_from,
            date_to=body.date_to,
            settings=s,
        ):
            yield {"event": ev["type"], "data": json.dumps(ev)}

    return EventSourceResponse(gen(), media_type="text/event-stream")
