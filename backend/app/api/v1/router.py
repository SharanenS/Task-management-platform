"""API v1 router."""

from fastapi import APIRouter

from app.api.v1 import auth, health

v1_router = APIRouter(prefix="/api/v1")

v1_router.include_router(health.router)
v1_router.include_router(auth.router)