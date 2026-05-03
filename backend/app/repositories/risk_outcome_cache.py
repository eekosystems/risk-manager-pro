from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.risk_outcome_cache import RiskOutcomeCache


class RiskOutcomeCacheRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def load_all(self) -> list[RiskOutcomeCache]:
        result = await self._db.execute(select(RiskOutcomeCache))
        return list(result.scalars().all())

    async def upsert(
        self,
        *,
        drive_item_id: str,
        cache_key: str,
        airport_identifier: str,
        source_file: str,
        risks_json: list[dict[str, Any]],
        risks_flagged_json: list[dict[str, Any]],
        notes_json: list[dict[str, Any]],
    ) -> None:
        stmt = pg_insert(RiskOutcomeCache).values(
            drive_item_id=drive_item_id,
            cache_key=cache_key,
            airport_identifier=airport_identifier,
            source_file=source_file,
            risks_json=risks_json,
            risks_flagged_json=risks_flagged_json,
            notes_json=notes_json,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[RiskOutcomeCache.drive_item_id],
            set_={
                "cache_key": stmt.excluded.cache_key,
                "airport_identifier": stmt.excluded.airport_identifier,
                "source_file": stmt.excluded.source_file,
                "risks_json": stmt.excluded.risks_json,
                "risks_flagged_json": stmt.excluded.risks_flagged_json,
                "notes_json": stmt.excluded.notes_json,
                "cached_at": stmt.excluded.cached_at,
            },
        )
        await self._db.execute(stmt)
        await self._db.commit()

    async def delete_missing(self, fresh_ids: set[str]) -> int:
        if not fresh_ids:
            stmt = delete(RiskOutcomeCache)
        else:
            stmt = delete(RiskOutcomeCache).where(RiskOutcomeCache.drive_item_id.notin_(fresh_ids))
        result = await self._db.execute(stmt)
        await self._db.commit()
        return getattr(result, "rowcount", 0) or 0
