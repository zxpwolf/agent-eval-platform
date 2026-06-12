"""Server-Sent Events (SSE) endpoint for real-time trace streaming.

Clients can subscribe to receive events when new traces are created
or updated, enabling live dashboard updates without polling.
"""

import asyncio
import json
import logging
import time
from typing import Any, AsyncGenerator, Dict, List, Set

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stream", tags=["streaming"])

# In-memory subscriber management
_subscribers: Dict[str, asyncio.Queue] = {}
_next_id = 0


def _get_subscriber_id() -> str:
    global _next_id
    _next_id += 1
    return str(_next_id)


def notify(event_type: str, data: Dict[str, Any]) -> None:
    """Push an event to all connected SSE subscribers.

    Call this from other parts of the application (e.g., after store_trace)
    to broadcast events.

    Args:
        event_type: Event type string (e.g., 'trace.created', 'trace.updated').
        data: Event payload dict.
    """
    message = json.dumps({"type": event_type, "data": data, "timestamp": time.time()})
    dead_ids = []
    for sub_id, queue in _subscribers.items():
        try:
            queue.put_nowait(message)
        except asyncio.QueueFull:
            dead_ids.append(sub_id)

    for sub_id in dead_ids:
        _subscribers.pop(sub_id, None)
        logger.info(f"Removed full subscriber {sub_id}")


async def _event_generator(request: Request) -> AsyncGenerator[str, None]:
    """Yield SSE-formatted events to the client."""
    sub_id = _get_subscriber_id()
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    _subscribers[sub_id] = queue
    logger.info(f"SSE subscriber {sub_id} connected ({len(_subscribers)} total)")

    try:
        # Send initial connection event
        yield f"data: {json.dumps({'type': 'connected', 'subscriber_id': sub_id})}\n\n"

        while True:
            if await request.is_disconnected():
                break
            try:
                message = await asyncio.wait_for(queue.get(), timeout=30.0)
                yield f"data: {message}\n\n"
            except asyncio.TimeoutError:
                # Send keepalive comment to prevent connection timeout
                yield ": keepalive\n\n"
    except asyncio.CancelledError:
        pass
    finally:
        _subscribers.pop(sub_id, None)
        logger.info(f"SSE subscriber {sub_id} disconnected ({len(_subscribers)} total)")


@router.get("/traces")
async def stream_traces(request: Request):
    """SSE endpoint for real-time trace events.

    Events:
    - trace.created: New trace stored
    - trace.updated: Existing trace updated
    - eval.run.progress: Evaluation run progress update
    - eval.run.completed: Evaluation run finished
    """
    return StreamingResponse(
        _event_generator(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/subscribers")
async def get_subscriber_count():
    """Get the number of active SSE subscribers (debug endpoint)."""
    return {"subscriber_count": len(_subscribers)}
