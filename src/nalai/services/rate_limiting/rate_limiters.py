"""Rate limiter implementations."""

import atexit
import fcntl
import json
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Any

from langchain_core.rate_limiters import BaseRateLimiter

from .interfaces import RateLimiterInterface

logger = logging.getLogger(__name__)


class FileLockRateLimiter(BaseRateLimiter, RateLimiterInterface):
    """A rate limiter that uses file locks for cross-process synchronization."""

    def __init__(
        self,
        requests_per_second: float,
        max_bucket_size: int,
        check_every_n_seconds: float = 0.1,
        file_path: str | None = None,
        max_retries: int = 3,
        retry_delay: float = 0.1,
    ):
        self.requests_per_second = requests_per_second
        self.max_bucket_size = max_bucket_size
        self.check_every_n_seconds = check_every_n_seconds
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        # Use a secure temporary directory for the lock file
        if file_path is None:
            temp_directory = tempfile.gettempdir()
            lock_file_name = f"bedrock_rate_limiter_{hash(str(requests_per_second))}_{max_bucket_size}.lock"
            self.file_path = os.path.join(temp_directory, lock_file_name)
        else:
            # Validate file path to prevent directory traversal
            self.file_path = os.path.abspath(file_path)
            if not self.file_path.startswith(tempfile.gettempdir()):
                raise ValueError(
                    "Rate limiter file must be in the system's temp directory"
                )

        self._ensure_file_exists()
        atexit.register(self._cleanup)

    def _cleanup(self):
        """Clean up resources on exit."""
        try:
            if hasattr(self, "file") and not self.file.closed:
                self.file.close()
        except Exception as error:
            logger.warning(f"Failed to cleanup rate limiter file: {error}")

    def _ensure_file_exists(self):
        """Create the lock file if it doesn't exist."""
        try:
            if not os.path.exists(self.file_path):
                Path(self.file_path).write_text(
                    json.dumps(
                        {
                            "tokens": self.max_bucket_size,
                            "last_update": time.time(),
                            "version": "1.0",
                        }
                    )
                )
                # Set restrictive permissions
                os.chmod(self.file_path, 0o600)
        except Exception as error:
            logger.error(f"Failed to create rate limiter file: {error}")
            raise

    def _acquire_lock(self) -> bool:
        """Acquire the file lock with retries."""
        for attempt in range(self.max_retries):
            try:
                # Ensure the lock file exists
                self._ensure_file_exists()

                # Try to acquire the lock
                self.lock_file = open(self.file_path, "r+")
                fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

                # Read current state
                try:
                    self.lock_file.seek(0)
                    file_content = self.lock_file.read().strip()
                    if file_content:
                        self.state = json.loads(file_content)
                except (json.JSONDecodeError, ValueError):
                    # If state is corrupted, repair it
                    self._repair_corrupted_state()

                return True
            except OSError as error:
                if self.lock_file:
                    self.lock_file.close()
                    self.lock_file = None
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                else:
                    logger.warning(
                        f"Failed to acquire lock after {self.max_retries} attempts: {error}"
                    )
                    return False
        return False

    def _release_lock(self) -> None:
        """Release the file lock and close the file."""
        if self.lock_file:
            try:
                # Write current state
                self.lock_file.seek(0)
                self.lock_file.truncate()
                json.dump(self.state, self.lock_file)
                self.lock_file.flush()

                # Release the lock
                fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_UN)
                self.lock_file.close()
            except Exception as error:
                logger.error(f"Error releasing lock: {error}")
            finally:
                self.lock_file = None

    def _repair_corrupted_state(self) -> None:
        """Repair a corrupted state file."""
        try:
            # Create a fresh state
            self.state = {"tokens": self.max_bucket_size, "last_update": time.time()}

            # Write the fresh state
            if self.lock_file:
                self.lock_file.seek(0)
                self.lock_file.truncate()
                json.dump(self.state, self.lock_file)
                self.lock_file.flush()

            logger.warning("Repaired corrupted state file")
        except Exception as error:
            logger.error(f"Failed to repair state file: {error}")
            raise

    def _validate_state(self, state: dict[str, Any]) -> bool:
        """Validate the state file contents."""
        required_keys = {"tokens", "last_update", "version"}
        if not all(key in state for key in required_keys):
            return False
        if not isinstance(state["tokens"], int | float):
            return False
        if not isinstance(state["last_update"], int | float):
            return False
        return True

    def _repair_state(self):
        """Repair corrupted state file."""
        try:
            Path(self.file_path).write_text(
                json.dumps(
                    {
                        "tokens": self.max_bucket_size,
                        "last_update": time.time(),
                        "version": "1.0",
                    }
                )
            )
            os.chmod(self.file_path, 0o600)
        except Exception as error:
            logger.error(f"Failed to repair rate limiter state: {error}")
            raise

    def acquire(self, tokens: int = 1, *, blocking: bool = True) -> bool:
        """
        Acquire tokens from the rate limiter.

        Args:
            tokens: Number of tokens to acquire (default: 1)
            blocking: If True, will retry until tokens are available or max retries reached
                     If False, will return immediately if tokens are not available

        Returns:
            bool: True if tokens were acquired, False otherwise
        """
        if not self._acquire_lock():
            return False

        try:
            current_time = time.time()

            # Update token count based on time passed
            time_passed = current_time - self.state["last_update"]
            if time_passed > 0:
                new_tokens = min(
                    self.max_bucket_size,
                    self.state["tokens"] + (time_passed * self.requests_per_second),
                )
                self.state["tokens"] = new_tokens
                self.state["last_update"] = current_time

            # Check if we have enough tokens
            if self.state["tokens"] >= tokens:
                self.state["tokens"] -= tokens
                return True

            if not blocking:
                return False

            # If blocking, wait and retry
            time.sleep(self.check_every_n_seconds)
            return self.acquire(tokens, blocking=blocking)

        finally:
            self._release_lock()

    async def aacquire(self, *, blocking: bool = True) -> bool:
        """
        Async version of acquire.

        Args:
            blocking: If True, will retry until tokens are available or max retries reached
                     If False, will return immediately if tokens are not available

        Returns:
            bool: True if tokens were acquired, False otherwise
        """
        return self.acquire(blocking=blocking)
