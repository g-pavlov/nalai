"""Unit tests for logging configuration module."""

import logging
import os
import tempfile
from unittest.mock import patch

import pytest

from api_assistant.utils.logging import (
    get_environment_log_level,
    get_log_level,
    is_debug_enabled,
    load_logging_config,
    setup_logging,
)


class TestLoggingConfig:
    """Test logging configuration functionality."""

    def test_get_environment_log_level_default(self):
        """Test default log level when no environment variable is set."""
        with patch.dict(os.environ, {}, clear=True):
            assert get_environment_log_level() == "INFO"

    def test_get_environment_log_level_from_log_level(self):
        """Test log level from LOG_LEVEL environment variable."""
        with (
            patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}, clear=True),
            patch("api_assistant.config.settings") as mock_settings,
        ):
            mock_settings.logging_level = "DEBUG"
            assert get_environment_log_level() == "DEBUG"

    def test_get_environment_log_level_from_debug_true(self):
        """Test log level from DEBUG=true environment variable."""
        with patch.dict(os.environ, {"DEBUG": "true"}, clear=True):
            assert get_environment_log_level() == "DEBUG"

    def test_get_environment_log_level_from_debug_false(self):
        """Test log level when DEBUG=false (should not override LOG_LEVEL)."""
        with (
            patch.dict(
                os.environ, {"DEBUG": "false", "LOG_LEVEL": "WARNING"}, clear=True
            ),
            patch("api_assistant.config.settings") as mock_settings,
        ):
            mock_settings.logging_level = "WARNING"
            assert get_environment_log_level() == "WARNING"

    def test_get_environment_log_level_case_insensitive(self):
        """Test that log level is converted to uppercase."""
        with (
            patch.dict(os.environ, {"LOG_LEVEL": "debug"}, clear=True),
            patch("api_assistant.config.settings") as mock_settings,
        ):
            mock_settings.logging_level = "debug"
            assert get_environment_log_level() == "DEBUG"

    def test_get_log_level(self):
        """Test get_log_level function."""
        with (
            patch.dict(os.environ, {"LOG_LEVEL": "ERROR"}, clear=True),
            patch("api_assistant.config.settings") as mock_settings,
        ):
            mock_settings.logging_level = "ERROR"
            assert get_log_level() == "ERROR"

    def test_is_debug_enabled_true(self):
        """Test is_debug_enabled when DEBUG is true."""
        with patch.dict(os.environ, {"DEBUG": "true"}, clear=True):
            assert is_debug_enabled() is True

    def test_is_debug_enabled_false(self):
        """Test is_debug_enabled when DEBUG is false."""
        with patch.dict(os.environ, {"DEBUG": "false"}, clear=True):
            assert is_debug_enabled() is False

    def test_is_debug_enabled_not_set(self):
        """Test is_debug_enabled when DEBUG is not set."""
        with patch.dict(os.environ, {}, clear=True):
            assert is_debug_enabled() is False

    def test_load_logging_config_file_not_found(self):
        """Test load_logging_config with non-existent file."""
        with pytest.raises(FileNotFoundError):
            load_logging_config("non_existent_file.yaml")

    def test_setup_logging_creates_loggers(self):
        """Test that setup_logging creates expected loggers."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("""
version: 1
formatters:
  simple:
    format: "%(message)s"
handlers:
  console:
    class: logging.StreamHandler
    formatter: simple
loggers:
  api-assistant:
    level: INFO
    handlers: [console]
    propagate: False
  api_assistant:
    level: INFO
    handlers: [console]
    propagate: False
  models:
    level: INFO
    handlers: [console]
    propagate: False
  config:
    level: INFO
    handlers: [console]
    propagate: False
root:
  level: INFO
  handlers: [console]
""")
            config_path = f.name

        try:
            with (
                patch.dict(os.environ, {"LOG_LEVEL": "INFO"}, clear=True),
                patch("api_assistant.config.settings") as mock_settings,
                patch("rich.logging.RichHandler", logging.StreamHandler),
            ):
                mock_settings.logging_level = "INFO"
                mock_settings.logging_directory = "/tmp/test_logs"
                setup_logging(config_path)

                # Check that loggers are created
                loggers = ["api-assistant", "api_assistant", "models", "config"]

                for logger_name in loggers:
                    logger = logging.getLogger(logger_name)
                    assert logger is not None
                    assert logger.getEffectiveLevel() == logging.INFO

        finally:
            os.unlink(config_path)

    def test_setup_logging_respects_environment_level(self):
        """Test that setup_logging respects LOG_LEVEL environment variable."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("""
version: 1
loggers:
  api-assistant:
    level: INFO
root:
  level: INFO
""")
            config_path = f.name

        try:
            with (
                patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}, clear=True),
                patch("api_assistant.config.settings") as mock_settings,
            ):
                mock_settings.logging_level = "DEBUG"
                mock_settings.logging_directory = "/tmp/test_logs"
                setup_logging(config_path)

                logger = logging.getLogger("api-assistant")
                assert logger.level == logging.DEBUG

        finally:
            os.unlink(config_path)

    def test_setup_logging_creates_log_directory(self):
        """Test that setup_logging creates log directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(os.environ, {"LOG_DIR": temp_dir}, clear=True):
                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".yaml", delete=False
                ) as f:
                    f.write("""
loggers:
  api-assistant:
    level: INFO
root:
  level: INFO
""")
                    config_path = f.name

                try:
                    setup_logging(config_path)
                    # Check that log directory exists
                    assert os.path.exists(temp_dir)
                finally:
                    os.unlink(config_path)

    def test_setup_logging_with_invalid_level(self):
        """Test that setup_logging handles invalid log levels gracefully."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("""
version: 1
loggers:
  api-assistant:
    level: INFO
root:
  level: INFO
""")
            config_path = f.name

        try:
            with (
                patch.dict(os.environ, {"LOG_LEVEL": "INVALID_LEVEL"}, clear=True),
                patch("api_assistant.config.settings") as mock_settings,
            ):
                mock_settings.logging_level = "INVALID_LEVEL"
                mock_settings.logging_directory = "/tmp/test_logs"
                setup_logging(config_path)

                # Should default to DEBUG for api-assistant logger
                logger = logging.getLogger("api-assistant")
                assert logger.level == logging.DEBUG

        finally:
            os.unlink(config_path)
