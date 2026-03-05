"""
Idempotent seed script for local development.

Populates the database with realistic aviation safety data for testing.
Uses uuid5 with a fixed namespace for deterministic, idempotent IDs.

Usage:
    cd backend && python -m scripts.seed
"""

import asyncio
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory, engine, Base
from app.models.audit import AuditEntry
from app.models.conversation import Conversation, ConversationStatus, FunctionType
from app.models.document import Document, DocumentStatus
from app.models.message import Message, MessageRole
from app.models.organization import Organization, OrganizationStatus
from app.models.organization_membership import MembershipRole, OrganizationMembership
from app.models.user import User

# Fixed namespace for deterministic UUIDs
NS = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")

# Organization IDs
DEMO_ORG_ID = uuid.uuid5(NS, "org-demo-org")
CLIENT_ORG_ID = uuid.uuid5(NS, "org-acme-aviation")


def _id(name: str) -> uuid.UUID:
    return uuid.uuid5(NS, name)


# ---------------------------------------------------------------------------
# Organizations
# ---------------------------------------------------------------------------

ORGANIZATIONS = [
    Organization(
        id=DEMO_ORG_ID,
        name="Demo Organization",
        slug="demo-org",
        status=OrganizationStatus.ACTIVE,
        is_platform=True,
    ),
    Organization(
        id=CLIENT_ORG_ID,
        name="Acme Aviation Services",
        slug="acme-aviation",
        status=OrganizationStatus.ACTIVE,
        is_platform=False,
    ),
]

# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

USERS = [
    User(
        id=_id("user-sarah"),
        entra_id="entra-sarah-chen",
        email="sarah.chen@example.com",
        display_name="Sarah Chen",
        is_platform_admin=True,
        is_active=True,
        last_login=datetime(2024, 12, 15, 10, 30, tzinfo=timezone.utc),
    ),
    User(
        id=_id("user-mike"),
        entra_id="entra-mike-rodriguez",
        email="mike.rodriguez@example.com",
        display_name="Mike Rodriguez",
        is_platform_admin=False,
        is_active=True,
        last_login=datetime(2024, 12, 14, 8, 0, tzinfo=timezone.utc),
    ),
    User(
        id=_id("user-emily"),
        entra_id="entra-emily-park",
        email="emily.park@example.com",
        display_name="Emily Park",
        is_platform_admin=False,
        is_active=True,
        last_login=datetime(2024, 12, 13, 16, 45, tzinfo=timezone.utc),
    ),
]

# ---------------------------------------------------------------------------
# Organization Memberships
# ---------------------------------------------------------------------------

MEMBERSHIPS = [
    # Sarah: org_admin at Demo Org (platform admin too)
    OrganizationMembership(
        id=_id("membership-sarah-fg"),
        user_id=_id("user-sarah"),
        organization_id=DEMO_ORG_ID,
        role=MembershipRole.ORG_ADMIN,
        is_active=True,
    ),
    # Sarah: org_admin at Acme (she manages client orgs)
    OrganizationMembership(
        id=_id("membership-sarah-acme"),
        user_id=_id("user-sarah"),
        organization_id=CLIENT_ORG_ID,
        role=MembershipRole.ORG_ADMIN,
        is_active=True,
    ),
    # Mike: analyst at Demo Org
    OrganizationMembership(
        id=_id("membership-mike-fg"),
        user_id=_id("user-mike"),
        organization_id=DEMO_ORG_ID,
        role=MembershipRole.ANALYST,
        is_active=True,
    ),
    # Emily: viewer at Demo Org
    OrganizationMembership(
        id=_id("membership-emily-fg"),
        user_id=_id("user-emily"),
        organization_id=DEMO_ORG_ID,
        role=MembershipRole.VIEWER,
        is_active=True,
    ),
    # Emily: analyst at Acme (different role in different org)
    OrganizationMembership(
        id=_id("membership-emily-acme"),
        user_id=_id("user-emily"),
        organization_id=CLIENT_ORG_ID,
        role=MembershipRole.ANALYST,
        is_active=True,
    ),
]

# ---------------------------------------------------------------------------
# Conversations
# ---------------------------------------------------------------------------

CONVERSATIONS = [
    Conversation(
        id=_id("conv-phl-runway"),
        user_id=_id("user-mike"),
        organization_id=DEMO_ORG_ID,
        title="PHL: Runway Incursion Risk Factors",
        function_type=FunctionType.PHL,
        status=ConversationStatus.ACTIVE,
    ),
    Conversation(
        id=_id("conv-sra-birdstrike"),
        user_id=_id("user-mike"),
        organization_id=DEMO_ORG_ID,
        title="SRA: Bird Strike Mitigation at KJFK",
        function_type=FunctionType.SRA,
        status=ConversationStatus.ACTIVE,
    ),
    Conversation(
        id=_id("conv-system-fuel"),
        user_id=_id("user-sarah"),
        organization_id=DEMO_ORG_ID,
        title="System Analysis: Fuel System Cross-Feed Valve",
        function_type=FunctionType.SYSTEM_ANALYSIS,
        status=ConversationStatus.ACTIVE,
    ),
    Conversation(
        id=_id("conv-general-sms"),
        user_id=_id("user-emily"),
        organization_id=DEMO_ORG_ID,
        title="SMS Implementation Questions",
        function_type=FunctionType.GENERAL,
        status=ConversationStatus.ACTIVE,
    ),
]

# ---------------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------------

MESSAGES = [
    # PHL Conversation
    Message(
        id=_id("msg-phl-1"),
        conversation_id=_id("conv-phl-runway"),
        role=MessageRole.USER,
        content=(
            "We're introducing a new taxiway intersection at our facility. "
            "Can you help identify potential runway incursion hazards associated "
            "with the new layout?"
        ),
    ),
    Message(
        id=_id("msg-phl-2"),
        conversation_id=_id("conv-phl-runway"),
        role=MessageRole.ASSISTANT,
        content=(
            "Based on FAA AC 150/5300-13B and historical runway incursion data, "
            "here are the key hazards to evaluate for a new taxiway intersection:\n\n"
            "## Identified Hazards\n\n"
            "1. **Hot Spot Creation** — New taxiway intersections near runway thresholds "
            "create potential confusion points for pilots and vehicle operators.\n\n"
            "2. **Signage/Marking Ambiguity** — Transitional geometry may require "
            "non-standard signage that increases cognitive load.\n\n"
            "3. **Line-of-Sight Obstructions** — Equipment or structures near the "
            "intersection may obstruct ATC tower sightlines.\n\n"
            "4. **Communication Errors** — New intersection designators added to "
            "taxi instructions increase readback/hearback error risk.\n\n"
            "5. **Vehicle/Pedestrian Exposure** — Construction phase increases "
            "unauthorized surface movement risk.\n\n"
            "## Recommended Next Steps\n\n"
            "- Conduct a tabletop exercise with ATC, pilots, and ground crews\n"
            "- Review the intersection against FAA Runway Incursion Mitigation (RIM) criteria\n"
            "- Develop a NOTAM communication plan for the transition period"
        ),
        citations=[
            {
                "source": "FAA AC 150/5300-13B",
                "section": "Chapter 4 — Taxiway Design",
                "content": "Taxiway intersections should minimize the potential for pilot confusion...",
                "score": 0.94,
                "chunk_id": "faa_ac150_5300_13b_4",
            },
            {
                "source": "FAA InFO 16012",
                "section": "Runway Incursion Prevention",
                "content": "Hot spots are locations on an airport movement area with a history of...",
                "score": 0.89,
                "chunk_id": "faa_info_16012_1",
            },
        ],
    ),
    # SRA Conversation
    Message(
        id=_id("msg-sra-1"),
        conversation_id=_id("conv-sra-birdstrike"),
        role=MessageRole.USER,
        content=(
            "We need to conduct a Safety Risk Assessment for bird strike risk "
            "during approach to Runway 31L at JFK. What severity and likelihood "
            "should we assign?"
        ),
    ),
    Message(
        id=_id("msg-sra-2"),
        conversation_id=_id("conv-sra-birdstrike"),
        role=MessageRole.ASSISTANT,
        content=(
            "Based on FAA Order 8040.4B and the FAA Wildlife Strike Database, here is "
            "the recommended risk assessment for bird strikes on approach to KJFK 31L:\n\n"
            "## Risk Assessment\n\n"
            "| Factor | Rating | Rationale |\n"
            "|--------|--------|-----------|\n"
            "| **Severity** | 4 — Hazardous | Engine ingestion during approach can result "
            "in power loss and forced landing |\n"
            "| **Likelihood** | B — Probable | KJFK averages 200+ wildlife strikes/year; "
            "31L approach crosses Jamaica Bay wildlife refuge |\n"
            "| **Risk Level** | **High** | Severity 4 × Likelihood B = High (5×5 matrix) |\n\n"
            "## Recommended Mitigations\n\n"
            "1. Coordinate with USDA Wildlife Services for Jamaica Bay habitat management\n"
            "2. Deploy avian radar (MERLIN or equivalent) for real-time bird detection\n"
            "3. Establish seasonal approach altitude modifications during peak migration\n"
            "4. Brief all crews on bird strike go-around procedures for 31L"
        ),
        citations=[
            {
                "source": "FAA Order 8040.4B",
                "section": "Safety Risk Management Process",
                "content": "Risk assessment shall use the 5x5 severity-likelihood matrix...",
                "score": 0.96,
                "chunk_id": "faa_8040_4b_ch5_1",
            },
            {
                "source": "ICAO Annex 19",
                "section": "Chapter 5 — Safety Data Collection",
                "content": "Wildlife strike reporting is essential for safety risk management...",
                "score": 0.88,
                "chunk_id": "icao_annex19_ch5_2",
            },
        ],
    ),
    # System Analysis Conversation
    Message(
        id=_id("msg-sys-1"),
        conversation_id=_id("conv-system-fuel"),
        role=MessageRole.USER,
        content=(
            "We're analyzing the cross-feed valve in a light jet fuel system. "
            "What failure modes should we consider?"
        ),
    ),
    Message(
        id=_id("msg-sys-2"),
        conversation_id=_id("conv-system-fuel"),
        role=MessageRole.ASSISTANT,
        content=(
            "For a cross-feed valve system safety analysis per ARP 4761 methodology:\n\n"
            "## Failure Modes\n\n"
            "1. **Valve fails closed** — Unable to transfer fuel between tanks, "
            "leading to fuel imbalance and potential engine fuel starvation\n"
            "2. **Valve fails open** — Unintended fuel transfer, potential asymmetric "
            "fuel loading, center of gravity shift\n"
            "3. **Valve partial blockage** — Reduced flow rate, insufficient for "
            "single-engine operation from opposite tank\n"
            "4. **Position indicator malfunction** — Crew unaware of actual valve state\n"
            "5. **Electrical actuator failure** — Valve stuck in last position\n\n"
            "Each failure mode should be evaluated against FAR 25.901 and 25.981 requirements."
        ),
        citations=[
            {
                "source": "SAE ARP 4761",
                "section": "Functional Hazard Assessment",
                "content": "Each function and its associated failure conditions shall be...",
                "score": 0.92,
                "chunk_id": "sae_arp4761_fha_1",
            },
        ],
    ),
    # General SMS Conversation
    Message(
        id=_id("msg-gen-1"),
        conversation_id=_id("conv-general-sms"),
        role=MessageRole.USER,
        content="What are the four pillars of an SMS?",
    ),
    Message(
        id=_id("msg-gen-2"),
        conversation_id=_id("conv-general-sms"),
        role=MessageRole.ASSISTANT,
        content=(
            "The four pillars (components) of a Safety Management System per "
            "ICAO Annex 19 and FAA AC 120-92B are:\n\n"
            "1. **Safety Policy and Objectives** — Management commitment, safety "
            "accountability, appointment of key safety personnel, coordination of "
            "emergency response planning, SMS documentation\n\n"
            "2. **Safety Risk Management (SRM)** — Hazard identification, risk "
            "assessment using 5×5 matrices, risk mitigation and controls\n\n"
            "3. **Safety Assurance (SA)** — Safety performance monitoring, management "
            "of change, continuous improvement of the SMS\n\n"
            "4. **Safety Promotion** — Training and education, safety communication "
            "to foster a positive safety culture"
        ),
        citations=[
            {
                "source": "FAA AC 120-92B",
                "section": "Chapter 1 — SMS Framework",
                "content": "An SMS consists of four components...",
                "score": 0.97,
                "chunk_id": "faa_ac120_92b_ch1_1",
            },
            {
                "source": "ICAO Annex 19",
                "section": "Chapter 4 — SMS Framework",
                "content": "The four components of an SMS are: safety policy...",
                "score": 0.93,
                "chunk_id": "icao_annex19_ch4_1",
            },
        ],
    ),
]

# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

DOCUMENTS = [
    Document(
        id=_id("doc-faa-ac120"),
        organization_id=DEMO_ORG_ID,
        uploaded_by=_id("user-sarah"),
        filename="FAA_AC_120-92B_SMS_Guide.pdf",
        blob_path=f"{DEMO_ORG_ID}/{_id('doc-faa-ac120')}/FAA_AC_120-92B_SMS_Guide.pdf",
        content_type="application/pdf",
        size_bytes=2_500_000,
        status=DocumentStatus.INDEXED,
        chunk_count=48,
    ),
    Document(
        id=_id("doc-icao-annex19"),
        organization_id=DEMO_ORG_ID,
        uploaded_by=_id("user-sarah"),
        filename="ICAO_Annex_19_Safety_Management.pdf",
        blob_path=f"{DEMO_ORG_ID}/{_id('doc-icao-annex19')}/ICAO_Annex_19_Safety_Management.pdf",
        content_type="application/pdf",
        size_bytes=3_100_000,
        status=DocumentStatus.INDEXED,
        chunk_count=62,
    ),
    Document(
        id=_id("doc-faa-8040"),
        organization_id=DEMO_ORG_ID,
        uploaded_by=_id("user-mike"),
        filename="FAA_Order_8040_4B_SRM_Policy.pdf",
        blob_path=f"{DEMO_ORG_ID}/{_id('doc-faa-8040')}/FAA_Order_8040_4B_SRM_Policy.pdf",
        content_type="application/pdf",
        size_bytes=1_800_000,
        status=DocumentStatus.PROCESSING,
        chunk_count=0,
    ),
    Document(
        id=_id("doc-company-sop"),
        organization_id=DEMO_ORG_ID,
        uploaded_by=_id("user-mike"),
        filename="Company_Safety_SOP_v3.docx",
        blob_path=f"{DEMO_ORG_ID}/{_id('doc-company-sop')}/Company_Safety_SOP_v3.docx",
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        size_bytes=450_000,
        status=DocumentStatus.FAILED,
        chunk_count=0,
        error_message="Failed to extract text: file corrupted at page 12",
    ),
    Document(
        id=_id("doc-hazard-log"),
        organization_id=DEMO_ORG_ID,
        uploaded_by=_id("user-emily"),
        filename="Hazard_Tracking_Log_2024.txt",
        blob_path=f"{DEMO_ORG_ID}/{_id('doc-hazard-log')}/Hazard_Tracking_Log_2024.txt",
        content_type="text/plain",
        size_bytes=85_000,
        status=DocumentStatus.UPLOADED,
        chunk_count=0,
    ),
]

# ---------------------------------------------------------------------------
# Audit Entries
# ---------------------------------------------------------------------------

AUDIT_ENTRIES = [
    AuditEntry(
        id=_id("audit-1"),
        user_id=_id("user-sarah"),
        action="document.uploaded",
        resource_type="document",
        resource_id=str(_id("doc-faa-ac120")),
        ip_address="10.0.1.50",
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0",
        correlation_id=_id("corr-1"),
        outcome="success",
        organization_id=DEMO_ORG_ID,
    ),
    AuditEntry(
        id=_id("audit-2"),
        user_id=_id("user-mike"),
        action="chat.message_sent",
        resource_type="conversation",
        resource_id=str(_id("conv-phl-runway")),
        ip_address="10.0.1.51",
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/120.0",
        correlation_id=_id("corr-2"),
        outcome="success",
        organization_id=DEMO_ORG_ID,
    ),
    AuditEntry(
        id=_id("audit-3"),
        user_id=_id("user-emily"),
        action="user.profile_viewed",
        resource_type="user",
        resource_id=str(_id("user-emily")),
        ip_address="10.0.1.52",
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) Firefox/121.0",
        correlation_id=_id("corr-3"),
        outcome="success",
        organization_id=DEMO_ORG_ID,
    ),
]


# ---------------------------------------------------------------------------
# Seed runner
# ---------------------------------------------------------------------------


async def _upsert(db: AsyncSession, model_class: type, instances: list[object]) -> int:
    """Insert records that don't already exist (idempotent by primary key)."""
    created = 0
    for instance in instances:
        pk = getattr(instance, "id")
        existing = await db.get(model_class, pk)
        if existing is None:
            db.add(instance)
            created += 1
    await db.flush()
    return created


async def seed() -> None:
    print("Seeding database...")

    async with async_session_factory() as db:
        try:
            orgs_created = await _upsert(db, Organization, ORGANIZATIONS)
            print(f"  Organizations: {orgs_created} created ({len(ORGANIZATIONS)} total)")

            users_created = await _upsert(db, User, USERS)
            print(f"  Users: {users_created} created ({len(USERS)} total)")

            memberships_created = await _upsert(db, OrganizationMembership, MEMBERSHIPS)
            print(f"  Memberships: {memberships_created} created ({len(MEMBERSHIPS)} total)")

            convos_created = await _upsert(db, Conversation, CONVERSATIONS)
            print(f"  Conversations: {convos_created} created ({len(CONVERSATIONS)} total)")

            msgs_created = await _upsert(db, Message, MESSAGES)
            print(f"  Messages: {msgs_created} created ({len(MESSAGES)} total)")

            docs_created = await _upsert(db, Document, DOCUMENTS)
            print(f"  Documents: {docs_created} created ({len(DOCUMENTS)} total)")

            audit_created = await _upsert(db, AuditEntry, AUDIT_ENTRIES)
            print(f"  Audit entries: {audit_created} created ({len(AUDIT_ENTRIES)} total)")

            await db.commit()
            print("Seed complete.")

        except Exception as e:
            await db.rollback()
            print(f"Seed failed: {e}")
            raise


if __name__ == "__main__":
    asyncio.run(seed())
