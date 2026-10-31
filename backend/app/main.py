from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import router
from app.core.config import BACKEND_DIR, Settings
from app.db.session import create_db_engine, create_session_factory


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings if settings is not None else Settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        engine = create_db_engine(settings.database_url)
        application.state.session_factory = create_session_factory(engine)
        try:
            yield
        finally:
            engine.dispose()

    application = FastAPI(
        title="SubCadence API", version="0.1.0", lifespan=lifespan,
        docs_url=None, redoc_url=None,
    )
    application.mount(
        "/docs-assets", StaticFiles(directory=BACKEND_DIR / "app" / "static" / "swagger-ui"),
        name="docs-assets",
    )

    @application.get("/docs", include_in_schema=False)
    def documentation() -> HTMLResponse:
        return get_swagger_ui_html(
            openapi_url="/openapi.json", title="SubCadence API - Swagger UI",
            swagger_js_url="/docs-assets/swagger-ui-bundle.js",
            swagger_css_url="/docs-assets/swagger-ui.css",
            swagger_favicon_url="/docs-assets/favicon-32x32.png",
            swagger_ui_parameters={"validatorUrl": None},
        )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )
    application.include_router(router)
    return application


app = create_app()


def run() -> None:
    import uvicorn

    settings = Settings()
    uvicorn.run("app.main:app", host=settings.api_host, port=settings.api_port)
