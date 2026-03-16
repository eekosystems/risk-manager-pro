from fastapi import APIRouter

from app.api.v1.analytics import router as analytics_router
from app.api.v1.chat import router as chat_router
from app.api.v1.documents import router as documents_router
from app.api.v1.health import router as health_router
from app.api.v1.organizations import router as organizations_router
from app.api.v1.risks import router as risks_router
from app.api.v1.settings import router as settings_router
from app.api.v1.users import router as users_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_router)
api_router.include_router(users_router)
api_router.include_router(chat_router)
api_router.include_router(documents_router)
api_router.include_router(organizations_router)
api_router.include_router(risks_router)
api_router.include_router(settings_router)
api_router.include_router(analytics_router)
