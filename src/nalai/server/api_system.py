from fastapi import FastAPI

from .schemas import HealthzResponse


def create_server_api(app: FastAPI) -> None:
    """Create basic endpoint routes."""

    @app.get("/healthz", tags=["System"])
    async def healthz() -> HealthzResponse:
        return HealthzResponse(status="Healthy")

    # TODO: Add /metrics endpoint for future metrics collection
    # @app.get("/metrics")
    # async def metrics() -> dict[str, object]:
    #     return {"metrics": "to be implemented"}
