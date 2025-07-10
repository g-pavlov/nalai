from datetime import UTC, datetime

from langchain_core.tools import tool


@tool("CurrentUTCTimeTool")
def get_current_utc_time() -> str:
    """Returns the current UTC time"""
    return datetime.now(UTC)
