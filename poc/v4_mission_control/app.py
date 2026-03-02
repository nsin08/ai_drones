"""FastAPI bootstrap for Mission Control v4."""

from fastapi import FastAPI

from .api.routes import router as api_router
from .config import get_settings


def create_app() -> FastAPI:
    """Create the isolated v4 FastAPI app."""

    settings = get_settings()
    app = FastAPI(
        title="Mission Control v4",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.include_router(api_router)
    app.state.environment = settings.ENVIRONMENT
    return app


app = create_app()
