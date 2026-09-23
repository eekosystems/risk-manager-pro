"""SP3 residual re-assessment lifecycle.

A mitigation change queues a run, the run proposes a residual cell, and only
a person's confirmation writes it to the risk entry. A run that is
superseded while in flight, or whose answer fails validation, never becomes
a proposal.
"""

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.residual_assessment import ResidualAssessment, ResidualAssessmentStatus
from app.models.risk import Mitigation, RiskEntry, RiskLevel, compute_risk_level
from app.models.user import User
from app.services.rag import SearchResult
from app.services.residual_assessment import ResidualAssessmentRunner, ResidualAssessmentService
from tests.conftest import make_test_organization, make_test_user

_TIERS = ("Avoid/Eliminate", "Substitute", "Engineer", "Administrative", "PPE")


class _TestSessionFactory:
    """Hands the runner the test's transaction-bound session instead of a new one."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    @asynccontextmanager
    async def __call__(self) -> AsyncIterator[AsyncSession]:
        yield self._session


class _QueuedRuns(ResidualAssessmentRunner):
    """Records queued runs instead of calling the model."""

    def __init__(self) -> None:
        self.queued: list[uuid.UUID] = []

    async def run(self, assessment_id: uuid.UUID, organization_id: uuid.UUID) -> None:
        self.queued.append(assessment_id)


def _answer(engineer_cell: str | None = "D2", admin_cell: str | None = "E2") -> str:
    cells = {"Engineer": engineer_cell, "Administrative": admin_cell}
    return json.dumps(
        {
            "tiers": [
                {
                    "tier": name,
                    "applied": cells.get(name) is not None,
                    "controls": (
                        f"{name} control"
                        if cells.get(name)
                        else "Not applicable -- nothing recorded"
                    ),
                    "residual_cell": cells.get(name),
                }
                for name in _TIERS
            ],
            "alarp_status": "ALARP achieved",
            "rationale": "Escort and NOTAM reduce exposure per the DEN precedent.",
            "sources": ["DEN SRMD 2024.pdf"],
            "insufficient_basis": False,
        }
    )


async def _seed(db: AsyncSession) -> tuple[RiskEntry, User]:
    org = make_test_organization(org_id=uuid.uuid4())
    user = make_test_user()
    db.add_all([org, user])
    await db.flush()
    entry = RiskEntry(
        organization_id=org.id,
        created_by=user.id,
        title="Haul route crossing",
        description="Imported",
        hazard="Contractors and Haul Rts. - Accident between AC and Veh.",
        severity=4,
        likelihood="C",
        risk_level=compute_risk_level(4, "C"),
        airport_identifier="DEN",
    )
    db.add(entry)
    await db.flush()
    db.add(Mitigation(risk_entry_id=entry.id, title="Escort haul vehicles", description="Escort"))
    await db.flush()
    return entry, user


def _runner(db: AsyncSession, answer: str | Exception) -> tuple[ResidualAssessmentRunner, Any]:
    openai = AsyncMock()
    if isinstance(answer, Exception):
        openai.chat_completion.side_effect = answer
    else:
        openai.chat_completion.return_value = answer
    rag = AsyncMock()
    rag.hybrid_search.return_value = [
        SearchResult(
            content="Escort reduced likelihood to D.",
            source="DEN SRMD 2024.pdf",
            score=1.0,
            chunk_id="doc_1",
        )
    ]
    runner = ResidualAssessmentRunner(_TestSessionFactory(db), openai, rag)  # type: ignore[arg-type]
    return runner, openai


async def _pending(db: AsyncSession, entry: RiskEntry, user: User) -> ResidualAssessment:
    assessment = ResidualAssessment(
        organization_id=entry.organization_id,
        risk_entry_id=entry.id,
        status=ResidualAssessmentStatus.PENDING,
        trigger="mitigation.created",
        requested_by=user.id,
    )
    db.add(assessment)
    await db.flush()
    return assessment


async def test_request_supersedes_the_open_run_and_queues_a_new_one(
    db_session: AsyncSession,
) -> None:
    entry, user = await _seed(db_session)
    runs = _QueuedRuns()
    service = ResidualAssessmentService(db_session, runs)

    first = await service.request(entry.id, entry.organization_id, user.id, "mitigation.created")
    second = await service.request(entry.id, entry.organization_id, user.id, "mitigation.updated")
    await db_session.refresh(first)

    assert first.status == ResidualAssessmentStatus.SUPERSEDED
    assert second.status == ResidualAssessmentStatus.PENDING
    assert second.trigger == "mitigation.updated"
    for _ in range(3):  # let the queued tasks start
        await asyncio.sleep(0)
    assert runs.queued == [first.id, second.id]


async def test_request_for_another_tenants_entry_is_not_found(db_session: AsyncSession) -> None:
    entry, user = await _seed(db_session)
    with pytest.raises(NotFoundError):
        await ResidualAssessmentService(db_session, _QueuedRuns()).request(
            entry.id, uuid.uuid4(), user.id, "manual"
        )


async def test_run_proposes_without_touching_the_entry(db_session: AsyncSession) -> None:
    entry, user = await _seed(db_session)
    assessment = await _pending(db_session, entry, user)
    runner, openai = _runner(db_session, _answer())

    await runner.run(assessment.id, entry.organization_id)

    assert assessment.status == ResidualAssessmentStatus.PROPOSED
    assert (assessment.residual_likelihood, assessment.residual_severity) == ("E", 4)
    assert assessment.residual_risk_level == RiskLevel.MEDIUM
    assert assessment.result_json is not None
    assert assessment.result_json["sources"] == ["DEN SRMD 2024.pdf"]
    assert entry.residual_likelihood is None
    prompt = openai.chat_completion.call_args.args[0][1]["content"]
    assert "Escort haul vehicles" in prompt
    assert "C2 (Remote / Hazardous) -- High" in prompt


@pytest.mark.parametrize(
    ("answer", "code"),
    [
        ("not json", "INVALID_RESULT"),
        (_answer(engineer_cell="B1"), "INVALID_RESULT"),
        (
            json.dumps({"insufficient_basis": True, "rationale": "No precedent"}),
            "INSUFFICIENT_BASIS",
        ),
        (RuntimeError("deployment unavailable"), "LLM_ERROR"),
    ],
)
async def test_run_failures_are_recorded(
    db_session: AsyncSession, answer: str | Exception, code: str
) -> None:
    entry, user = await _seed(db_session)
    assessment = await _pending(db_session, entry, user)
    runner, _ = _runner(db_session, answer)

    await runner.run(assessment.id, entry.organization_id)

    assert assessment.status == ResidualAssessmentStatus.FAILED
    assert assessment.error_code == code
    assert assessment.residual_likelihood is None


async def test_run_superseded_in_flight_is_discarded(db_session: AsyncSession) -> None:
    entry, user = await _seed(db_session)
    assessment = await _pending(db_session, entry, user)
    runner, openai = _runner(db_session, _answer())

    async def supersede_then_answer(*_: Any, **__: Any) -> str:
        assessment.status = ResidualAssessmentStatus.SUPERSEDED
        await db_session.flush()
        return _answer()

    openai.chat_completion.side_effect = supersede_then_answer
    await runner.run(assessment.id, entry.organization_id)

    assert assessment.status == ResidualAssessmentStatus.SUPERSEDED
    assert assessment.residual_likelihood is None


async def test_confirm_writes_the_residual_to_the_entry(db_session: AsyncSession) -> None:
    entry, user = await _seed(db_session)
    assessment = await _pending(db_session, entry, user)
    runner, _ = _runner(db_session, _answer())
    await runner.run(assessment.id, entry.organization_id)
    service = ResidualAssessmentService(db_session, _QueuedRuns())

    confirmed = await service.confirm(entry.id, assessment.id, entry.organization_id, user.id)

    assert confirmed.status == ResidualAssessmentStatus.CONFIRMED
    assert confirmed.decided_by == user.id
    assert (entry.residual_likelihood, entry.residual_severity) == ("E", 4)
    assert entry.residual_risk_level == RiskLevel.MEDIUM
    with pytest.raises(ConflictError):
        await service.confirm(entry.id, assessment.id, entry.organization_id, user.id)


async def test_pending_run_cannot_be_confirmed(db_session: AsyncSession) -> None:
    entry, user = await _seed(db_session)
    assessment = await _pending(db_session, entry, user)
    with pytest.raises(ConflictError):
        await ResidualAssessmentService(db_session, _QueuedRuns()).confirm(
            entry.id, assessment.id, entry.organization_id, user.id
        )


async def test_dismiss_leaves_the_entry_unchanged(db_session: AsyncSession) -> None:
    entry, user = await _seed(db_session)
    assessment = await _pending(db_session, entry, user)
    runner, _ = _runner(db_session, _answer())
    await runner.run(assessment.id, entry.organization_id)

    dismissed = await ResidualAssessmentService(db_session, _QueuedRuns()).dismiss(
        entry.id, assessment.id, entry.organization_id, user.id
    )

    assert dismissed.status == ResidualAssessmentStatus.DISMISSED
    assert entry.residual_likelihood is None


async def test_latest_assessment_per_entry(db_session: AsyncSession) -> None:
    entry, user = await _seed(db_session)
    service = ResidualAssessmentService(db_session, _QueuedRuns())
    await service.request(entry.id, entry.organization_id, user.id, "mitigation.created")
    latest = await service.request(entry.id, entry.organization_id, user.id, "manual")

    found = await service.latest_for_entries([entry.id], entry.organization_id)

    assert found[entry.id].id == latest.id
    assert await service.latest_for_entries([entry.id], uuid.uuid4()) == {}
