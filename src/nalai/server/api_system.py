from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from .schemas import HealthzResponse


def create_server_api(app: FastAPI) -> None:
    """Create basic endpoint routes."""

    @app.get("/", include_in_schema=False)
    async def redirect_root_to_docs() -> RedirectResponse:
        return RedirectResponse("/docs")

    @app.get("/ui", include_in_schema=False)
    async def redirect_ui_to_index() -> RedirectResponse:
        return RedirectResponse("/ui/index.html")

    @app.get("/healthz", tags=["Server"])
    async def healthz() -> HealthzResponse:
        return HealthzResponse(status="Healthy")

    # TODO: Add /metrics endpoint for future metrics collection
    # @app.get("/metrics")
    # async def metrics() -> dict[str, object]:
    #     return {"metrics": "to be implemented"}
