"""Root API router - includes all sub-routers."""

from fastapi import APIRouter

from fourdpocket.api.admin import router as admin_router
from fourdpocket.api.ai import router as ai_router
from fourdpocket.api.auth import router as auth_router
from fourdpocket.api.collections import router as collections_router
from fourdpocket.api.comments import router as comments_router
from fourdpocket.api.feeds import router as feeds_router
from fourdpocket.api.highlights import router as highlights_router
from fourdpocket.api.import_export import router as import_export_router
from fourdpocket.api.items import router as items_router
from fourdpocket.api.notes import item_notes_router
from fourdpocket.api.notes import router as notes_router
from fourdpocket.api.rss import router as rss_router
from fourdpocket.api.rules import router as rules_router
from fourdpocket.api.saved_filters import router as saved_filters_router
from fourdpocket.api.search import router as search_router
from fourdpocket.api.settings import router as settings_router
from fourdpocket.api.sharing import public_router
from fourdpocket.api.sharing import router as sharing_router
from fourdpocket.api.stats import router as stats_router
from fourdpocket.api.tags import router as tags_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth_router)
api_router.include_router(items_router)
api_router.include_router(notes_router)
api_router.include_router(item_notes_router)
api_router.include_router(tags_router)
api_router.include_router(collections_router)
api_router.include_router(search_router)
api_router.include_router(ai_router)
api_router.include_router(import_export_router)
api_router.include_router(sharing_router)
api_router.include_router(comments_router)
api_router.include_router(feeds_router)
api_router.include_router(public_router)
api_router.include_router(admin_router)
api_router.include_router(settings_router)
api_router.include_router(stats_router)
api_router.include_router(rules_router)
api_router.include_router(highlights_router)
api_router.include_router(rss_router)
api_router.include_router(saved_filters_router)
