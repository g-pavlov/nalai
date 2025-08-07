"""Interfaces for rate limiters."""

from abc import abstractmethod
from typing import Protocol

from pydantic import BaseModel, Field


class RateLimiterConfig(BaseModel):
    """Configuration for rate limiters."""

    requests_per_second: float = Field(
        default=1.0, description="Number of requests allowed per second"
    )
    max_bucket_size: int = Field(
        default=1, description="Maximum number of tokens in the bucket"
    )
    check_every_n_seconds: float = Field(
        default=1.0, description="How often to check and refill the bucket"
    )
    file_path: str | None = Field(
        default=None, description="Optional file path for file-based rate limiters"
    )


class RateLimiterInterface(Protocol):
    """Interface for rate limiters."""

    @abstractmethod
    def acquire(self, *, blocking: bool = True) -> bool:
        """Acquire a token from the rate limiter."""
        pass

    @abstractmethod
    async def aacquire(self, *, blocking: bool = True) -> bool:
        """Asynchronously acquire a token from the rate limiter."""
        pass


class RateLimiterFactoryInterface(Protocol):
    """Interface for rate limiter factories."""

    @abstractmethod
    def create_rate_limiter(
        self, model_platform: str, model: str, config: RateLimiterConfig
    ) -> RateLimiterInterface:
        """Create a rate limiter instance."""
        pass
