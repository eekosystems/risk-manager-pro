from datetime import datetime
from typing import Any

from sqlalchemy import String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RiskOutcomeCache(Base):
    __tablename__ = "risk_outcome_cache"

    drive_item_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    cache_key: Mapped[str] = mapped_column(String(500))
    airport_identifier: Mapped[str] = mapped_column(String(50), index=True)
    source_file: Mapped[str] = mapped_column(String(500))
    risks_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    risks_flagged_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    notes_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    cached_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())
