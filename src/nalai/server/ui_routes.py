import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger("nalai")


def create_ui_route(app: FastAPI) -> None:
    """Create basic endpoint routes."""

    @app.get("/ui", include_in_schema=False)
    async def redirect_ui_to_index() -> RedirectResponse:
        return RedirectResponse("/ui/index.html")

    # Mount UI static files
    ui_path = Path(__file__).parent.parent.parent.parent / "demo" / "ui"
    logger.debug(f"Attempting to mount UI from path: {ui_path}")

    if ui_path.exists():
        app.mount("/ui", StaticFiles(directory=str(ui_path)), name="ui")
        logger.debug(f"Mounted UI static files from {ui_path}")
    else:
        logger.warning(f"UI directory not found at {ui_path}")
        # Try alternative paths
        alt_paths = [
            Path.cwd() / "demo" / "ui",
            Path.cwd()
            / "src"
            / "nalai"
            / "server"
            / ".."
            / ".."
            / ".."
            / ".."
            / "demo"
            / "ui",
        ]
        for alt_path in alt_paths:
            logger.info(f"Trying alternative path: {alt_path}")
            if alt_path.exists():
                app.mount("/ui", StaticFiles(directory=str(alt_path)), name="ui")
                logger.info(
                    f"Mounted UI static files from alternative path: {alt_path}"
                )
                break
