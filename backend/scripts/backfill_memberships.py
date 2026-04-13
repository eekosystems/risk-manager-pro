"""Backfill OrganizationMembership rows so RBAC rollout does not lock users out.

Gives every active user without a membership an ORG_ADMIN role in the org
passed as --org-id (or every organization if --all-orgs is set). Idempotent.

Usage:
    cd backend && python -m scripts.backfill_memberships --org-id <uuid>
    cd backend && python -m scripts.backfill_memberships --all-orgs
"""

import argparse
import asyncio
import uuid

from sqlalchemy import select

from app.core.database import async_session_factory
from app.models.organization import Organization
from app.models.organization_membership import MembershipRole, OrganizationMembership
from app.models.user import User


async def _backfill_org(session, organization_id: uuid.UUID) -> int:
    users_result = await session.execute(select(User).where(User.is_active.is_(True)))
    users = list(users_result.scalars().all())

    existing_result = await session.execute(
        select(OrganizationMembership.user_id).where(
            OrganizationMembership.organization_id == organization_id
        )
    )
    existing_user_ids = {row for row in existing_result.scalars().all()}

    created = 0
    for user in users:
        if user.id in existing_user_ids:
            continue
        session.add(
            OrganizationMembership(
                user_id=user.id,
                organization_id=organization_id,
                role=MembershipRole.ORG_ADMIN,
                is_active=True,
            )
        )
        created += 1
    return created


async def _run(org_id: uuid.UUID | None, all_orgs: bool) -> None:
    async with async_session_factory() as session:
        if all_orgs:
            orgs_result = await session.execute(select(Organization.id))
            org_ids = list(orgs_result.scalars().all())
        elif org_id is not None:
            org_ids = [org_id]
        else:
            raise SystemExit("Pass --org-id <uuid> or --all-orgs")

        total = 0
        for oid in org_ids:
            created = await _backfill_org(session, oid)
            total += created
            print(f"{oid}: created {created} memberships")
        await session.commit()
        print(f"done: {total} memberships created across {len(org_ids)} orgs")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--org-id", type=uuid.UUID, default=None)
    parser.add_argument("--all-orgs", action="store_true")
    args = parser.parse_args()
    asyncio.run(_run(args.org_id, args.all_orgs))


if __name__ == "__main__":
    main()
