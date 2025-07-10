import json
import logging.config
import logging.handlers
import os
from datetime import datetime
from typing import Any

import yaml
from rich.console import Console
from rich.theme import Theme


class RichFormatter(logging.Formatter):
    """Custom formatter that adds emojis and colors to console logs."""

    def __init__(self):
        super().__init__()
        self.console = Console(
            theme=Theme(
                {
                    "info": "cyan",
                    "warning": "yellow",
                    "error": "red",
                    "critical": "red bold",
                    "debug": "dim",
                }
            )
        )

        # Emoji mapping for different log levels
        self.level_emojis = {
            logging.DEBUG: "🔍",
            logging.INFO: "ℹ️",
            logging.WARNING: "⚠️",
            logging.ERROR: "❌",
            logging.CRITICAL: "🚨",
        }

        # Color mapping for different loggers
        self.logger_colors = {
            "api-assistant": "blue",
            "api_assistant": "green",
            "models": "magenta",
            "config": "cyan",
            "uvicorn": "yellow",
            "fastapi": "blue",
        }

    def format(self, record):
        # Get emoji for log level
        emoji = self.level_emojis.get(record.levelno, "📝")

        # Get color for logger
        logger_color = self.logger_colors.get(record.name, "white")

        # Use rich markup for all log levels
        message = f"{emoji} [{logger_color}]{record.name}[/{logger_color}] {record.getMessage()}"
        return message


class StructuredFileFormatter(logging.Formatter):
    """Formatter for structured JSON logs in files."""

    def format(self, record):
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Add extra fields if present
        if hasattr(record, "taskName") and record.taskName:
            log_entry["task"] = record.taskName

        return json.dumps(log_entry)


def load_logging_config(config_path: str = "logging.yaml") -> dict[str, Any]:
    """
    Load logging configuration from YAML file with environment variable substitution.

    Args:
        config_path: Path to the logging configuration YAML file

    Returns:
        Dictionary containing the logging configuration
    """
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Logging configuration file not found: {config_path}")

    with open(config_path) as config_file:
        config = yaml.safe_load(config_file)

    return config


def get_environment_log_level() -> str:
    """
    Get the current log level from settings.

    Returns:
        Log level string (default: INFO)
    """
    from ..config import settings

    # Support DEBUG=true as a shortcut for LOG_LEVEL=DEBUG
    if os.getenv("DEBUG", "").lower() == "true":
        return "DEBUG"
    return settings.logging_level.upper()


def setup_logging(config_path: str = "logging.yaml") -> None:
    """
    Set up logging configuration with environment variable support.

    Args:
        config_path: Path to the logging configuration YAML file
    """
    try:
        config = load_logging_config(config_path)

        # Get the desired log level from environment variable
        current_log_level = get_environment_log_level()

        # Use system log directory for production containers
        from ..config import settings

        log_directory = settings.logging_directory
        os.makedirs(log_directory, exist_ok=True)

        # Initialize formatters and handlers if they don't exist
        if "formatters" not in config:
            config["formatters"] = {}
        if "handlers" not in config:
            config["handlers"] = {}

        # Add structured formatter for file logging
        config["formatters"]["structured"] = {
            "()": "api_assistant.utils.logging.StructuredFileFormatter"
        }

        # Add file handler for structured logging
        config["handlers"]["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": f"{log_directory}/app.log",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5,
            "formatter": "structured",
        }

        # Update loggers to use both console and file handlers
        if "loggers" in config:
            for logger_name, logger_config in config["loggers"].items():
                if logger_name in [
                    "api-assistant",
                    "api_assistant",
                    "models",
                    "config",
                ]:
                    # These loggers default to DEBUG but can be overridden
                    logger_config["level"] = (
                        current_log_level
                        if current_log_level
                        in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
                        else "DEBUG"
                    )
                elif logger_name in ["uvicorn", "fastapi"]:
                    # These loggers default to INFO but can be overridden
                    logger_config["level"] = (
                        current_log_level
                        if current_log_level in ["INFO", "WARNING", "ERROR", "CRITICAL"]
                        else "INFO"
                    )

                # Add file handler to existing handlers
                existing_handlers = logger_config.get("handlers", ["console"])
                if "file" not in existing_handlers:
                    existing_handlers.append("file")
                logger_config["handlers"] = existing_handlers

        # Update root logger level and handlers
        if "root" in config:
            config["root"]["level"] = (
                current_log_level
                if current_log_level
                in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
                else "INFO"
            )
            # Add file handler to existing root handlers
            existing_root_handlers = config["root"].get("handlers", ["console"])
            if "file" not in existing_root_handlers:
                existing_root_handlers.append("file")
            config["root"]["handlers"] = existing_root_handlers

        # Apply the configuration
        logging.config.dictConfig(config)

        # Get the root logger to log the configuration
        logger = logging.getLogger("api-assistant")
        logger.info(f"Logging configured with level: {current_log_level}")

    except Exception as error:
        # Fallback to basic logging if configuration fails
        current_log_level = get_environment_log_level()
        level = getattr(logging, current_log_level, logging.INFO)

        logging.basicConfig(
            level=level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        logging.error(f"Failed to load logging configuration: {error}")


def get_log_level() -> str:
    """
    Get the current log level from environment variable.

    Returns:
        Log level string (default: INFO)
    """
    return get_environment_log_level()


def is_debug_enabled() -> bool:
    """
    Check if debug logging is enabled.

    Returns:
        True if LOG_LEVEL is DEBUG, False otherwise
    """
    return get_log_level() == "DEBUG"
