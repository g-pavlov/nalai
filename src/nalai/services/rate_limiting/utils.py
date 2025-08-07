"""Rate limiter utilities."""

import fcntl
import os
import sys
import tempfile
import time
from pathlib import Path

from ...config import settings
from .interfaces import RateLimiterInterface


# Use a session-based directory structure
def get_session_id() -> str:
    """Get or create a session ID that's shared across all processes."""
    session_file_path = (
        Path(tempfile.gettempdir()) / "rate_limiter_debug" / ".current_session"
    )
    base_directory = session_file_path.parent
    base_directory.mkdir(parents=True, exist_ok=True)

    # Try to read existing session ID with file lock
    if session_file_path.exists():
        try:
            with open(session_file_path) as session_file_handle:
                fcntl.flock(session_file_handle.fileno(), fcntl.LOCK_SH)
                try:
                    return session_file_handle.read().strip()
                finally:
                    fcntl.flock(session_file_handle.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass

    # Create new session ID with exclusive lock
    session_id = str(int(time.time()))
    try:
        with open(session_file_path, "w") as session_file_handle:
            fcntl.flock(session_file_handle.fileno(), fcntl.LOCK_EX)
            try:
                session_file_handle.write(session_id)
                session_file_handle.flush()
                os.fsync(session_file_handle.fileno())
            finally:
                fcntl.flock(session_file_handle.fileno(), fcntl.LOCK_UN)
    except Exception:
        return session_id

    return session_id


def get_debug_directory() -> Path:
    """Get the session-specific directory for storing debug logs."""
    session_id = get_session_id()
    debug_directory = (
        Path(tempfile.gettempdir()) / "rate_limiter_debug" / f"session_{session_id}"
    )
    debug_directory.mkdir(parents=True, exist_ok=True)
    return debug_directory


DEBUG_DIR = get_debug_directory()
DEBUG_LOG_PATH = DEBUG_DIR / f"process_{os.getpid()}.log"

# Immediate write on module import
try:
    with open(DEBUG_DIR / "module_import.log", "a") as module_import_file:
        fcntl.flock(module_import_file.fileno(), fcntl.LOCK_EX)
        try:
            module_import_file.write(f"Module imported at {os.getpid()}\n")
            module_import_file.flush()
            os.fsync(module_import_file.fileno())
        finally:
            fcntl.flock(module_import_file.fileno(), fcntl.LOCK_UN)
except Exception:
    pass


def _write_debug_message(message: str):
    """Write debug message to the debug log file."""
    try:
        with open(DEBUG_LOG_PATH, "a") as debug_file_handle:
            fcntl.flock(debug_file_handle.fileno(), fcntl.LOCK_EX)
            try:
                debug_file_handle.write(f"[PID {os.getpid()}] {message}\n")
                debug_file_handle.flush()
                os.fsync(debug_file_handle.fileno())
            finally:
                fcntl.flock(debug_file_handle.fileno(), fcntl.LOCK_UN)
    except Exception:
        pass


def is_test_environment() -> bool:
    """Check if we're running in a test environment."""
    result = (
        "pytest" in sys.modules
        or "test" in sys.argv[0]
        or "deepeval" in sys.modules
        or settings.cross_process_rate_limiter_enabled
    )
    _write_debug_message(
        f"Test environment check: pytest={bool('pytest' in sys.modules)}, test={bool('test' in sys.argv[0])}, deepeval={bool('deepeval' in sys.modules)}, xproc={settings.enable_cross_process_rate_limiter}, result={result}"
    )
    return result


def get_default_rate_limiter_class() -> type[RateLimiterInterface]:
    """Get the default rate limiter class based on the environment."""
    is_test = is_test_environment()
    enable_cross_process = settings.cross_process_rate_limiter_enabled
    _write_debug_message(
        f"Getting rate limiter class: is_test={is_test}, enable_cross_process={enable_cross_process}"
    )

    if is_test or enable_cross_process:
        from .rate_limiters import FileLockRateLimiter

        _write_debug_message("Selected FileLockRateLimiter")
        # Log when FileLockRateLimiter is actually instantiated
        original_init = FileLockRateLimiter.__init__

        def wrapped_init(self, *args, **kwargs):
            _write_debug_message(
                f"FileLockRateLimiter instantiated with args={args}, kwargs={kwargs}"
            )
            return original_init(self, *args, **kwargs)

        FileLockRateLimiter.__init__ = wrapped_init
        return FileLockRateLimiter
    else:
        from langchain_core.rate_limiters import InMemoryRateLimiter

        _write_debug_message("Selected InMemoryRateLimiter")
        return InMemoryRateLimiter
