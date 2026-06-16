"""FastAPI application factory."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.api.routes.health import router as health_router
from services.api.routes.twilio import router as twilio_router
from services.config import settings
from services.db.database import init_db

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(
        title="SlotBot",
        description="Real-time voice AI receptionist for Indian clinics",
        version="0.1.0",
        docs_url="/docs" if settings.environment == "development" else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(twilio_router)
    app.include_router(health_router)

    @app.on_event("startup")
    async def startup() -> None:
        logger.info("SlotBot starting up (env=%s)", settings.environment)
        await init_db()
        logger.info("Database ready")

    @app.on_event("shutdown")
    async def shutdown() -> None:
        logger.info("SlotBot shutting down")

    return app


app = create_app()
