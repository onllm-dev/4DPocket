"""Root API router — includes all sub-routers."""

from fastapi import APIRouter

from fourdpocket.api.ai import router as ai_router
from fourdpocket.api.auth import router as auth_router
from fourdpocket.api.collections import router as collections_router
from fourdpocket.api.items import router as items_router
from fourdpocket.api.notes import item_notes_router, router as notes_router
from fourdpocket.api.search import router as search_router
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
