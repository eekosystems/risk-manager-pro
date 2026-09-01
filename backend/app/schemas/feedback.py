import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.conversation import FunctionType
from app.models.feedback import FeedbackRating, FeedbackStatus
from app.models.guidance import GuidanceScope


class SubmitFeedbackRequest(BaseModel):
    conversation_id: uuid.UUID
    message_id: uuid.UUID
    rating: FeedbackRating
    comment: str = Field(min_length=1, max_length=5000)


class FeedbackResponse(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    message_id: uuid.UUID
    rating: FeedbackRating
    status: FeedbackStatus
    comment: str
    created_at: datetime

    model_config = {"from_attributes": True}


class FeedbackReviewItem(BaseModel):
    """A feedback entry with the output it refers to, for the review queue."""

    id: uuid.UUID
    organization_id: uuid.UUID
    conversation_id: uuid.UUID
    message_id: uuid.UUID
    rating: FeedbackRating
    status: FeedbackStatus
    comment: str
    submitted_by: uuid.UUID
    submitter_name: str
    message_excerpt: str
    review_note: str | None
    reviewed_at: datetime | None
    created_at: datetime


class ReviewFeedbackRequest(BaseModel):
    status: FeedbackStatus
    review_note: str | None = Field(default=None, max_length=1000)


class PromoteFeedbackRequest(BaseModel):
    """Turn a piece of feedback into a guidance rule."""

    content: str = Field(min_length=1, max_length=2000)
    scope: GuidanceScope = GuidanceScope.ORGANIZATION
    function_type: FunctionType | None = None


class GuidanceResponse(BaseModel):
    id: uuid.UUID
    scope: GuidanceScope
    organization_id: uuid.UUID | None
    function_type: FunctionType | None
    content: str
    source_feedback_id: uuid.UUID | None
    is_active: bool
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CreateGuidanceRequest(BaseModel):
    content: str = Field(min_length=1, max_length=2000)
    scope: GuidanceScope = GuidanceScope.GLOBAL
    organization_id: uuid.UUID | None = None
    function_type: FunctionType | None = None


class UpdateGuidanceRequest(BaseModel):
    content: str | None = Field(default=None, min_length=1, max_length=2000)
    is_active: bool | None = None
    function_type: FunctionType | None = None
    # Explicit flag, since None on function_type means "leave unchanged".
    applies_to_all_functions: bool = False
