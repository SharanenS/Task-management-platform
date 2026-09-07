"""V1 API router — aggregates all sub-routers."""

from fastapi import APIRouter

from app.api.v1 import auth, health, notifications, projects, reports, users

v1_router = APIRouter(prefix="/api/v1")

v1_router.include_router(health.router)
v1_router.include_router(auth.router)
v1_router.include_router(users.router)
v1_router.include_router(projects.router)
v1_router.include_router(reports.router)
v1_router.include_router(notifications.router)