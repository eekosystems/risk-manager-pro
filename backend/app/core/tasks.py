import asyncio

import structlog

logger = structlog.get_logger(__name__)

_background_tasks: set[asyncio.Task[None]] = set()


def track_task(task: asyncio.Task[None]) -> None:
    """Register a background task for graceful shutdown tracking."""
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


async def drain_all_tasks() -> None:
    """Await all pending background tasks. Call during graceful shutdown."""
    if _background_tasks:
        logger.info("draining_background_tasks", count=len(_background_tasks))
        await asyncio.gather(*_background_tasks, return_exceptions=True)
        _background_tasks.clear()
