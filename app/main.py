import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.core.config import settings
from app.core.logging_config import logger
from app.core.database import init_db

from app.api.routes.health import router as health_router
from app.api.routes.announcements import router as announcements_router
from app.api.routes.chat import router as chat_router
from app.api.routes.feed import router as feed_router
from app.api.routes.feedback import router as feedback_router
from app.api.routes.students import router as students_router
from app.api.routes.ums import router as ums_router

from fastapi.middleware.cors import CORSMiddleware

import asyncio
from app.services.ums_sync_service import UMSSyncService

async def background_sync_worker():
    """Initial startup sync and periodic background sync worker."""
    await asyncio.sleep(2)
    logger.info("Triggering automatic startup sync for live LPU announcements...")
    try:
        await asyncio.to_thread(UMSSyncService().run_sync, triggered_by="startup_auto_sync", limit=25)
        logger.info("Automatic startup sync completed successfully.")
    except Exception as exc:
        logger.warning("Startup auto-sync encountered notice: %s", exc)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle context manager to initialize database on startup and start auto-sync."""
    logger.info("Initializing LPU SmartNotice backend service...")
    init_db()
    sync_task = asyncio.create_task(background_sync_worker())
    yield
    sync_task.cancel()
    logger.info("Shutting down LPU SmartNotice backend service.")

app = FastAPI(
    title="LPU SmartNotice API",
    description="AI-Powered Personalized University Announcement Assistant API for Lovely Professional University.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Enable CORS for cross-origin integration (e.g. from ums.lpu.in browser sessions)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Routers under /api/v1
API_PREFIX = "/api/v1"
app.include_router(health_router, prefix=API_PREFIX)
app.include_router(announcements_router, prefix=API_PREFIX)
app.include_router(chat_router, prefix=API_PREFIX)
app.include_router(feed_router, prefix=API_PREFIX)
app.include_router(feedback_router, prefix=API_PREFIX)
app.include_router(students_router, prefix=API_PREFIX)
app.include_router(ums_router, prefix=API_PREFIX)
app.include_router(ums_router, prefix="/api")

# Static files for web frontend
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    @app.get("/", include_in_schema=False)
    async def serve_index():
        return FileResponse(os.path.join(static_dir, "index.html"))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
