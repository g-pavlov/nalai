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


class StructuredAuditFormatter(logging.Formatter):
    """Formatter for structured JSON audit logs following industry standards."""
    
    def format(self, record):
        # Expect structured data in record.audit_data or parse from message
        audit_data = getattr(record, 'audit_data', {})
        
        # If no audit_data attribute, try to parse from message as JSON
        if not audit_data and record.getMessage():
            try:
                audit_data = json.loads(record.getMessage())
            except json.JSONDecodeError:
                # Fallback: treat message as action
                audit_data = {"action": record.getMessage()}
        
        # Create standardized audit log entry
        audit_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "event_type": "audit",
            "severity": record.levelname,
            "logger": record.name,
            "action": audit_data.get("action", "unknown"),
            "user_id": audit_data.get("user_id"),
            "resource": audit_data.get("resource"),
            "success": audit_data.get("success", True),
            "metadata": audit_data.get("metadata", {}),
            "session_id": audit_data.get("session_id"),
            "request_id": audit_data.get("request_id"),
            "ip_address": audit_data.get("ip_address"),
            "user_agent": audit_data.get("user_agent"),
            "duration_ms": audit_data.get("duration_ms"),
            "status_code": audit_data.get("status_code"),
            "method": audit_data.get("method"),
            "path": audit_data.get("path"),
            "thread_id": audit_data.get("thread_id"),
        }
        
        # Remove None values for cleaner JSON
        audit_entry = {k: v for k, v in audit_entry.items() if v is not None}
        
        return json.dumps(audit_entry)


class AccessLogFormatter(logging.Formatter):
    """Formatter for HTTP access logs following standard web server format."""
    
    def format(self, record):
        # Parse access log message to extract structured data
        access_data = self._parse_access_message(record.getMessage())
        
        if not access_data:
            # Fallback: just return timestamp and message
            return f"{datetime.fromtimestamp(record.created).strftime('%d/%b/%Y:%H:%M:%S %z')} - {record.getMessage()}"
        
        # Format as standard HTTP access log (Apache combined format)
        timestamp = datetime.fromtimestamp(record.created).strftime('%d/%b/%Y:%H:%M:%S %z')
        remote_addr = access_data.get("remote_addr", "-")
        timestamp_str = f"[{timestamp}]"
        request = f'"{access_data.get("method", "-")} {access_data.get("path", "-")} HTTP/1.1"'
        status_code = access_data.get("status_code", "-")
        response_size = access_data.get("response_size", "-")
        referer = access_data.get("referer", "-")
        user_agent = access_data.get("user_agent", "-")
        response_time = access_data.get("response_time_ms", "-")
        
        # Apache combined log format with response time (no user_id for privacy)
        return f'{remote_addr} - - {timestamp_str} {request} {status_code} {response_size} "{referer}" "{user_agent}" {response_time}'
    
    def _parse_access_message(self, message: str) -> dict:
        """Parse access log message to extract structured data."""
        data = {}
        
        # Try to parse as JSON first (from middleware)
        try:
            json_data = json.loads(message)
            data.update(json_data)
            return data
        except json.JSONDecodeError:
            pass
        
        # Handle request messages: "Request: POST /api/agent from 192.168.1.1"
        if message.startswith("Request:"):
            parts = message.replace("Request:", "").strip().split(" from ")
            if len(parts) == 2:
                method_path = parts[0].strip()
                remote_addr = parts[1].strip()
                
                # Parse method and path
                if " " in method_path:
                    method, path = method_path.split(" ", 1)
                    data["method"] = method
                    data["path"] = path
                
                data["remote_addr"] = remote_addr
        
        # Handle response messages: "Response: 200 for POST /api/agent"
        elif message.startswith("Response:"):
            parts = message.replace("Response:", "").strip().split(" for ")
            if len(parts) == 2:
                status_code = parts[0].strip()
                method_path = parts[1].strip()
                
                try:
                    data["status_code"] = int(status_code)
                except ValueError:
                    pass
                
                # Parse method and path
                if " " in method_path:
                    method, path = method_path.split(" ", 1)
                    data["method"] = method
                    data["path"] = path
        
        return data


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

        # Add structured audit formatter
        config["formatters"]["structured_audit"] = {
            "()": "api_assistant.utils.logging.StructuredAuditFormatter"
        }

        # Add access log formatter
        config["formatters"]["access"] = {
            "()": "api_assistant.utils.logging.AccessLogFormatter"
        }

        # Add file handler for structured logging
        config["handlers"]["file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": f"{log_directory}/app.log",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5,
            "formatter": "structured",
        }

        # Update or add audit file handler to use structured formatter
        config["handlers"]["audit_file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": f"{log_directory}/audit.log",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 10,
            "formatter": "structured_audit",  # Use structured JSON format
        }

        # Add access log handler
        config["handlers"]["access_file"] = {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": f"{log_directory}/access.log",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 10,
            "formatter": "access",  # Use standard HTTP access log format
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
                elif logger_name == "api_assistant.audit":
                    # Audit logger always uses INFO level and only audit_file handler
                    logger_config["level"] = "INFO"
                    logger_config["handlers"] = ["audit_file"]
                    continue  # Skip the file handler addition for audit logger
                elif logger_name == "api_assistant.access":
                    # Access logger always uses INFO level and only access_file handler
                    logger_config["level"] = "INFO"
                    logger_config["handlers"] = ["access_file"]
                    continue  # Skip the file handler addition for access logger

                # Add file handler to existing handlers (except for audit logger)
                existing_handlers = logger_config.get("handlers", ["console"])
                if "file" not in existing_handlers:
                    existing_handlers.append("file")
                logger_config["handlers"] = existing_handlers
        
        # Add access logger if not present in config
        if "loggers" not in config:
            config["loggers"] = {}
        
        if "api_assistant.access" not in config["loggers"]:
            config["loggers"]["api_assistant.access"] = {
                "level": "INFO",
                "handlers": ["access_file"],
                "propagate": False
            }

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
        logger.debug(f"Logging configured with level: {current_log_level}")

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
