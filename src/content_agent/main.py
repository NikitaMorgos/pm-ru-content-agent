from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from content_agent.api.routes import jobs, tasks, webhooks
from content_agent.admin.routes import router as admin_router

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("content_agent.startup")
    yield
    logger.info("content_agent.shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title="PM-RU Content Agent",
        description="Automated pipeline for assembling marketplace product cards",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS – allow Figma plugin (null origin) and local dev
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Admin panel (serves SPA at /admin and API at /admin/api/*)
    app.include_router(admin_router, prefix="/admin", tags=["admin"])

    app.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
    app.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
    app.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])

    from fastapi.responses import RedirectResponse

    @app.get("/", include_in_schema=False)
    async def root_redirect() -> RedirectResponse:
        return RedirectResponse(url="/admin")

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
