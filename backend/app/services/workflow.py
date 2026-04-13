import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, NotFoundError
from app.models.workflow import Workflow, WorkflowStatus, WorkflowType
from app.schemas.workflow import CreateWorkflowRequest, UpdateWorkflowRequest


class WorkflowService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create(
        self,
        payload: CreateWorkflowRequest,
        user_id: uuid.UUID,
        organization_id: uuid.UUID,
    ) -> Workflow:
        workflow = Workflow(
            organization_id=organization_id,
            created_by=user_id,
            type=payload.type,
            title=payload.title,
            data=payload.data,
            conversation_id=payload.conversation_id,
        )
        self._db.add(workflow)
        await self._db.commit()
        await self._db.refresh(workflow)
        return workflow

    async def get(self, workflow_id: uuid.UUID, organization_id: uuid.UUID) -> Workflow:
        stmt = select(Workflow).where(
            Workflow.id == workflow_id,
            Workflow.organization_id == organization_id,
        )
        result = await self._db.execute(stmt)
        workflow = result.scalar_one_or_none()
        if not workflow:
            raise NotFoundError("Workflow", str(workflow_id))
        return workflow

    async def list_for_org(
        self,
        organization_id: uuid.UUID,
        type_filter: WorkflowType | None = None,
        status_filter: WorkflowStatus | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[Workflow], int]:
        from sqlalchemy import func

        base = select(Workflow).where(Workflow.organization_id == organization_id)
        if type_filter:
            base = base.where(Workflow.type == type_filter)
        if status_filter:
            base = base.where(Workflow.status == status_filter)

        count_stmt = select(func.count()).select_from(base.subquery())
        total = (await self._db.execute(count_stmt)).scalar_one()

        stmt = base.order_by(Workflow.created_at.desc()).offset(skip).limit(limit)
        result = await self._db.execute(stmt)
        return list(result.scalars().all()), total

    async def update(
        self,
        workflow_id: uuid.UUID,
        organization_id: uuid.UUID,
        payload: UpdateWorkflowRequest,
    ) -> Workflow:
        workflow = await self.get(workflow_id, organization_id)
        if workflow.status != WorkflowStatus.DRAFT:
            raise AppError(
                code="WORKFLOW_NOT_EDITABLE",
                message="Only draft workflows can be edited",
                status_code=409,
            )
        if payload.title is not None:
            workflow.title = payload.title
        if payload.data is not None:
            merged: dict[str, Any] = dict(workflow.data or {})
            merged.update(payload.data)
            workflow.data = merged
        await self._db.commit()
        await self._db.refresh(workflow)
        return workflow

    async def submit(self, workflow_id: uuid.UUID, organization_id: uuid.UUID) -> Workflow:
        workflow = await self.get(workflow_id, organization_id)
        if workflow.status != WorkflowStatus.DRAFT:
            raise AppError(
                code="WORKFLOW_NOT_SUBMITTABLE",
                message=f"Workflow is already {workflow.status.value}",
                status_code=409,
            )
        workflow.status = WorkflowStatus.SUBMITTED
        workflow.submitted_at = datetime.now(UTC)
        await self._db.commit()
        await self._db.refresh(workflow)
        return workflow

    async def approve(
        self,
        workflow_id: uuid.UUID,
        organization_id: uuid.UUID,
        approver_id: uuid.UUID,
        approve: bool,
    ) -> Workflow:
        workflow = await self.get(workflow_id, organization_id)
        if workflow.status != WorkflowStatus.SUBMITTED:
            raise AppError(
                code="WORKFLOW_NOT_APPROVABLE",
                message="Only submitted workflows can be approved or rejected",
                status_code=409,
            )
        workflow.status = WorkflowStatus.APPROVED if approve else WorkflowStatus.REJECTED
        workflow.approved_at = datetime.now(UTC)
        workflow.approved_by = approver_id

        if approve and workflow.type == WorkflowType.SRA:
            risk_entry_id = await self._spawn_risk_from_sra(workflow)
            if risk_entry_id is not None:
                workflow.risk_entry_id = risk_entry_id

        await self._db.commit()
        await self._db.refresh(workflow)
        return workflow

    async def delete(self, workflow_id: uuid.UUID, organization_id: uuid.UUID) -> None:
        workflow = await self.get(workflow_id, organization_id)
        if workflow.status not in (WorkflowStatus.DRAFT, WorkflowStatus.REJECTED):
            raise AppError(
                code="WORKFLOW_NOT_DELETABLE",
                message="Submitted or approved workflows cannot be deleted",
                status_code=409,
            )
        await self._db.delete(workflow)
        await self._db.commit()

    async def _spawn_risk_from_sra(self, workflow: Workflow) -> uuid.UUID | None:
        """Create a RiskEntry from an approved SRA workflow's structured data."""
        from app.models.risk import RiskEntry, compute_risk_level

        data = workflow.data or {}
        required = ("title", "description", "hazard", "severity", "likelihood")
        if not all(data.get(key) for key in required):
            return None

        try:
            severity = int(data["severity"])
        except (TypeError, ValueError):
            return None
        likelihood = str(data["likelihood"])
        if likelihood not in {"A", "B", "C", "D", "E"} or severity not in range(1, 6):
            return None

        entry = RiskEntry(
            organization_id=workflow.organization_id,
            created_by=workflow.created_by,
            title=str(data["title"])[:500],
            description=str(data["description"]),
            hazard=str(data["hazard"]),
            severity=severity,
            likelihood=likelihood,
            risk_level=compute_risk_level(severity, likelihood),
            function_type="sra",
            conversation_id=workflow.conversation_id,
            notes=data.get("notes"),
        )
        self._db.add(entry)
        await self._db.flush()
        return entry.id
