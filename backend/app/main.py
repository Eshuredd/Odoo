from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.router import router
from app.api.v1.dev import router as dev_router
from app.core.clock import Clock, utc_now
from app.core.config import BACKEND_DIR, Settings
from app.core.errors import ServiceError
from app.db.session import create_db_engine, create_session_factory
from app.services.mailer import Mailer, create_mailer


def create_app(
    settings: Settings | None = None, *, clock: Clock = utc_now, mailer: Mailer | None = None,
) -> FastAPI:
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
    application.state.settings = settings
    application.state.clock = clock
    application.state.mailer = mailer if mailer is not None else create_mailer(settings)

    @application.exception_handler(ServiceError)
    async def service_error(_request: Request, error: ServiceError) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code, content={"detail": error.detail},
            headers={"WWW-Authenticate": "Bearer"} if error.status_code == 401 else None,
        )

    @application.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, error: RequestValidationError) -> JSONResponse:
        # FastAPI normally echoes input values; credentials and raw reset tokens must not leak.
        details = [{key: item[key] for key in ("type", "loc", "msg")} for item in error.errors()]
        return JSONResponse(status_code=422, content={"detail": details})

    @application.exception_handler(SQLAlchemyError)
    async def database_error(_request: Request, _error: SQLAlchemyError) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": "Database unavailable"})

    @application.middleware("http")
    async def sensitive_response_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        if request.url.path.startswith(("/api/v1/auth", "/api/v1/dev/email-outbox")):
            response.headers["Cache-Control"] = "no-store"
        return response
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
    if settings.app_env == "development":
        application.include_router(dev_router)
    return application


app = create_app()


def run() -> None:
    import uvicorn

    settings = Settings()
    uvicorn.run("app.main:app", host=settings.api_host, port=settings.api_port)
