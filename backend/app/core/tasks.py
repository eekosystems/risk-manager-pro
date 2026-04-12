import asyncio
from collections import Counter

import structlog

logger = structlog.get_logger(__name__)

_background_tasks: set[asyncio.Task[None]] = set()
_task_failures: Counter[str] = Counter()


def track_task(task: asyncio.Task[None], *, name: str | None = None) -> None:
    """Register a background task for shutdown tracking and failure visibility.

    If the task raises, the failure is logged with ``alert_category="background_task_failure"``
    and counted per-name. Counts are exposed via ``get_task_failure_counts()`` for health
    reporting.
    """
    task_name = name or task.get_name()
    _background_tasks.add(task)
    task.add_done_callback(lambda t: _on_task_done(t, task_name))


def _on_task_done(task: asyncio.Task[None], name: str) -> None:
    _background_tasks.discard(task)
    if task.cancelled():
        return
    exc = task.exception()
    if exc is None:
        return
    _task_failures[name] += 1
    logger.error(
        "background_task_failed",
        task_name=name,
        alert_category="background_task_failure",
        exc_info=exc,
    )


def get_task_failure_counts() -> dict[str, int]:
    """Return a snapshot of background-task failure counts by name."""
    return dict(_task_failures)


async def drain_all_tasks() -> None:
    """Await all pending background tasks. Call during graceful shutdown."""
    if _background_tasks:
        logger.info("draining_background_tasks", count=len(_background_tasks))
        await asyncio.gather(*_background_tasks, return_exceptions=True)
        _background_tasks.clear()
