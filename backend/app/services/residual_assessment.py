"""SP3 residual re-assessment after a hazard's mitigations change.

A mitigation change queues a run; the run proposes a residual cell in the
background; an authorized user confirms or dismisses the proposal. Nothing
here writes the entry's residual except `confirm`, which keeps the Risk
Register rule that residual recalculations are confirmed by a person before
the record changes.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog

from app.core.exceptions import ConflictError, NotFoundError
from app.core.tasks import track_task
from app.models.residual_assessment import ResidualAssessment, ResidualAssessmentStatus
from app.models.risk import compute_risk_level
from app.repositories.residual_assessment import ResidualAssessmentRepository
from app.repositories.risk import RiskRepository
from app.services.residual_reassessment_engine import (
    Cell,
    ReassessmentRejectedError,
    build_messages,
    parse_reassessment,
)
from app.services.rr_sync import RRSyncService, _snapshot_entry, compute_entry_diff
from app.utils.json_payload import parse_json_payload

if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from app.services.openai_client import AzureOpenAIClient
    from app.services.rag import RAGService, SearchResult

logger = structlog.get_logger(__name__)

ERROR_LLM = "LLM_ERROR"
_PRECEDENT_COUNT = 5
_MAX_OUTPUT_TOKENS = 16000


def _naive_utc_now() -> datetime:
    # Timestamp columns are timezone-naive UTC, as func.now() writes them.
    return datetime.now(UTC).replace(tzinfo=None)


class ResidualAssessmentRunner:
    """Runs one queued re-assessment against Azure OpenAI and stores the proposal."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        openai_client: AzureOpenAIClient,
        rag_service: RAGService,
    ) -> None:
        self._session_factory = session_factory
        self._openai = openai_client
        self._rag = rag_service

    async def run(self, assessment_id: uuid.UUID, organization_id: uuid.UUID) -> None:
        # Read inputs and release the connection before the slow search and model calls.
        async with self._session_factory() as db:
            assessment = await ResidualAssessmentRepository(db).get_for_run(
                assessment_id, organization_id
            )
            if assessment is None or assessment.status != ResidualAssessmentStatus.PENDING:
                return
            entry = await RiskRepository(db).get_by_id(assessment.risk_entry_id, organization_id)
            if entry is None:
                return
            mitigations = sorted(entry.mitigations, key=lambda m: m.created_at)

        precedents = await self._precedents(entry.hazard, organization_id)
        messages = build_messages(entry, mitigations, precedents)
        initial = Cell(likelihood=entry.likelihood, severity=entry.severity)

        try:
            raw = await self._openai.chat_completion(
                messages, temperature=0.0, max_tokens=_MAX_OUTPUT_TOKENS, json_mode=True
            )
        except Exception:
            logger.error(
                "residual_assessment_llm_failed", assessment_id=str(assessment_id), exc_info=True
            )
            await self._finish_failed(assessment_id, organization_id, ERROR_LLM)
            return

        try:
            parsed = parse_reassessment(
                parse_json_payload(raw), initial, {p.source for p in precedents}
            )
        except ReassessmentRejectedError as exc:
            logger.warning(
                "residual_assessment_rejected",
                assessment_id=str(assessment_id),
                code=exc.code,
                detail=exc.detail,
            )
            await self._finish_failed(assessment_id, organization_id, exc.code)
            return

        async with self._session_factory() as db:
            assessment = await ResidualAssessmentRepository(db).get_for_run(
                assessment_id, organization_id
            )
            # A newer mitigation change superseded this run while it was in flight.
            if assessment is None or assessment.status != ResidualAssessmentStatus.PENDING:
                return
            assessment.status = ResidualAssessmentStatus.PROPOSED
            assessment.residual_severity = parsed.residual.severity
            assessment.residual_likelihood = parsed.residual.likelihood
            assessment.residual_risk_level = compute_risk_level(
                parsed.residual.severity, parsed.residual.likelihood
            )
            assessment.result_json = parsed.result.model_dump(mode="json")
            assessment.completed_at = _naive_utc_now()
            await db.commit()
        logger.info(
            "residual_assessment_proposed",
            assessment_id=str(assessment_id),
            residual=parsed.residual.label,
        )

    async def _precedents(self, hazard: str, organization_id: uuid.UUID) -> list[SearchResult]:
        try:
            return await self._rag.hybrid_search(
                f"{hazard} mitigation residual risk", organization_id, top_k=_PRECEDENT_COUNT
            )
        except Exception:
            # Precedents sharpen the estimate but are not required; the model is
            # told when none were retrieved and must say if that leaves no basis.
            logger.warning("residual_assessment_precedent_search_failed", exc_info=True)
            return []

    async def _finish_failed(
        self, assessment_id: uuid.UUID, organization_id: uuid.UUID, code: str
    ) -> None:
        async with self._session_factory() as db:
            assessment = await ResidualAssessmentRepository(db).get_for_run(
                assessment_id, organization_id
            )
            if assessment is None or assessment.status != ResidualAssessmentStatus.PENDING:
                return
            assessment.status = ResidualAssessmentStatus.FAILED
            assessment.error_code = code
            assessment.completed_at = _naive_utc_now()
            await db.commit()


class ResidualAssessmentService:
    def __init__(self, db: AsyncSession, runner: ResidualAssessmentRunner) -> None:
        self._db = db
        self._runner = runner
        self._repo = ResidualAssessmentRepository(db)
        self._risks = RiskRepository(db)
        self._sync = RRSyncService(db)

    async def request(
        self,
        risk_id: uuid.UUID,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
        trigger: str,
    ) -> ResidualAssessment:
        """Queue a run over the entry's current mitigations, replacing any open one."""
        entry = await self._risks.get_by_id(risk_id, organization_id)
        if entry is None:
            raise NotFoundError("RiskEntry", str(risk_id))
        await self._repo.supersede_open(risk_id, organization_id)
        assessment = await self._repo.create(
            organization_id=organization_id,
            risk_entry_id=risk_id,
            status=ResidualAssessmentStatus.PENDING,
            trigger=trigger,
            requested_by=user_id,
            # Stamped here rather than by now(), which is fixed per transaction,
            # so runs requested in one transaction still order newest-first.
            created_at=_naive_utc_now(),
        )
        # The run reads this row from its own session, so it must be committed
        # (with the mitigation change that triggered it) before the run starts.
        await self._db.commit()
        task = asyncio.create_task(self._runner.run(assessment.id, organization_id))
        track_task(task, name="risk.residual_assessment")
        logger.info(
            "residual_assessment_requested",
            assessment_id=str(assessment.id),
            risk_id=str(risk_id),
            trigger=trigger,
        )
        return assessment

    async def confirm(
        self,
        risk_id: uuid.UUID,
        assessment_id: uuid.UUID,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> ResidualAssessment:
        """Apply a proposed residual to the entry on an authorized user's say-so."""
        assessment = await self._get(risk_id, assessment_id, organization_id)
        if assessment.status != ResidualAssessmentStatus.PROPOSED:
            raise ConflictError(
                f"Only a proposed residual can be confirmed; this one is {assessment.status.value}."
            )
        entry = await self._risks.get_by_id(risk_id, organization_id)
        if entry is None:
            raise NotFoundError("RiskEntry", str(risk_id))

        before = _snapshot_entry(entry)
        entry.residual_severity = assessment.residual_severity
        entry.residual_likelihood = assessment.residual_likelihood
        entry.residual_risk_level = assessment.residual_risk_level
        self._decide(assessment, ResidualAssessmentStatus.CONFIRMED, user_id)
        await self._db.flush()

        diff = compute_entry_diff(before, entry)
        if diff:
            await self._sync.enqueue_update_push(entry=entry, diff=diff, initiator_user_id=user_id)
        logger.info(
            "residual_assessment_confirmed",
            assessment_id=str(assessment_id),
            risk_id=str(risk_id),
        )
        return assessment

    async def dismiss(
        self,
        risk_id: uuid.UUID,
        assessment_id: uuid.UUID,
        organization_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> ResidualAssessment:
        assessment = await self._get(risk_id, assessment_id, organization_id)
        if assessment.status not in (
            ResidualAssessmentStatus.PROPOSED,
            ResidualAssessmentStatus.FAILED,
        ):
            raise ConflictError(
                f"This re-assessment is {assessment.status.value} and cannot be dismissed."
            )
        self._decide(assessment, ResidualAssessmentStatus.DISMISSED, user_id)
        await self._db.flush()
        logger.info("residual_assessment_dismissed", assessment_id=str(assessment_id))
        return assessment

    async def latest_for_entries(
        self, risk_entry_ids: list[uuid.UUID], organization_id: uuid.UUID
    ) -> dict[uuid.UUID, ResidualAssessment]:
        return await self._repo.latest_for_entries(risk_entry_ids, organization_id)

    async def _get(
        self, risk_id: uuid.UUID, assessment_id: uuid.UUID, organization_id: uuid.UUID
    ) -> ResidualAssessment:
        assessment = await self._repo.get(assessment_id, risk_id, organization_id)
        if assessment is None:
            raise NotFoundError("ResidualAssessment", str(assessment_id))
        return assessment

    @staticmethod
    def _decide(
        assessment: ResidualAssessment, status: ResidualAssessmentStatus, user_id: uuid.UUID
    ) -> None:
        assessment.status = status
        assessment.decided_by = user_id
        assessment.decided_at = _naive_utc_now()
