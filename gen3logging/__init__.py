"""
Logging with a standardized format
"""

import json
import logging
import os
import sys
import time
from typing import Optional

FORMAT = "[%(asctime)s][%(name)10s][%(levelname)7s] %(message)s"

JSON_LOGS_ENV_VAR = "GEN3_JSON_LOGS"

_TRUTHY = frozenset({"1", "true", "t", "yes", "y", "on"})

_OTEL_FIELDS = (
    ("trace_id", "otelTraceID"),
    ("span_id", "otelSpanID"),
    ("service", "otelServiceName"),
)


class TextFormatter(logging.Formatter):
    """
    Format records with a %-style template, appending trace context.

    The trace suffix is appended only when OpenTelemetry supplied usable
    correlation ids, so output is unchanged from a plain logging.Formatter
    whenever no trace is recording.
    """

    def format(self, record: logging.LogRecord) -> str:
        """
        Render a record as text, with a trace suffix when one is available.

        Args:
            record (logging.LogRecord): record to format.

        Returns:
            str: the formatted line.
        """

        return super().format(record) + _trace_suffix(record)


class JsonFormatter(logging.Formatter):
    """
    Format log records as single-line JSON objects.

    OpenTelemetry correlation fields are read off the record when present and
    emitted as null otherwise, so records format correctly whether or not
    opentelemetry-instrumentation-logging is installed and instrumenting.
    """

    # gmtime pairs with the trailing Z in default_msec_format; localtime would
    # label local times as UTC.
    converter = time.gmtime
    default_time_format = "%Y-%m-%dT%H:%M:%S"
    default_msec_format = "%s.%03dZ"

    def format(self, record: logging.LogRecord) -> str:
        """
        Render a record as a JSON object.

        Args:
            record (logging.LogRecord): record to format.

        Returns:
            str: single-line JSON object.
        """

        payload = {
            "timestamp": self.formatTime(record, self.datefmt),
            "logger": record.name,
            "level": record.levelname,
            "message": record.getMessage(),
            **_otel_fields(record),
        }

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack_info"] = self.formatStack(record.stack_info)

        # default=str keeps a non-serializable value from raising inside a log call
        return json.dumps(payload, default=str)


def get_stream_handler(
    format: Optional[str] = None, json_logs: Optional[bool] = None
) -> logging.StreamHandler:
    """
    Return a stdout stream handler

    All logs will write to stdout.

    Args:
        format (Optional[str]): %-style format string. Defaults to
                                FORMAT. Ignored when JSON is enabled.
        json_logs (Optional[bool]): emit JSON instead of text. When None, falls
                                    back to the GEN3_JSON_LOGS env var.

    Returns:
        logging.StreamHandler: pre-formatted stream handler
    """

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_get_formatter(format, json_logs))

    return handler


def get_file_handler(
    file_name: str, format: Optional[str] = None, json_logs: Optional[bool] = None
) -> logging.FileHandler:
    """
    Return a file handler

    Args:
        file_name (str): name of file to write logs to
        format (Optional[str]): %-style format string. Defaults to
                                FORMAT. Ignored when JSON is enabled.
        json_logs (Optional[bool]): emit JSON instead of text. When None, falls
                                    back to the GEN3_JSON_LOGS env var.

    Returns:
        logging.FileHandler: pre-formatted file handler
    """

    handler = logging.FileHandler(file_name)
    handler.setFormatter(_get_formatter(format, json_logs))

    return handler


def get_logger(
    logger_name: str,
    file_name: Optional[str] = None,
    log_level: Optional[str] = None,
    format: Optional[str] = None,
    json_logs: Optional[bool] = None,
) -> logging.Logger:
    """
    Return an opinionated basic logger named `name` that logs to stdout

    If you leave the log level argument as None and the logger was not
    previously instantiated, the level will be set to NOTSET. If the logger
    was previously instantiated, the level will be left alone.

    If the level is NOTSET, then ancestor loggers are traversed and searched
    for a log_level and handler. See python docs.

    If you change the log level to something other than debug (or notset) then it will not
    display log statements below that level (see example and chart below for details).
    Ideally this should be handled by your application's command line args.

    eg:
    ```
    log = get_logger('hi', log_level='info')
    log.debug('hello world') # <- this will not display
    ```

    Args:
        logger_name (str): name of the logger
        file_name (Optional[str]): if present, will write logs to file as well
        log_level (Optional[str]): level of logging for this logger. string so you
                                   don't have to import logging in the application
        format (Optional[str]): %-style format string. Defaults to
                                FORMAT. Ignored when JSON is enabled.
        json_logs (Optional[bool]): emit JSON instead of text. When None, falls
                                    back to the GEN3_JSON_LOGS env var.

    Returns:
        logging.Logger: pre-formatted logger object

    Raises:
        Exception: if log_level is not one of the supported level names.
    """

    log_levels = {  # sorted level
        "notset": logging.NOTSET,  # 00
        "debug": logging.DEBUG,  # 10
        "info": logging.INFO,  # 20
        "warning": logging.WARNING,  # 30
        "warn": logging.WARNING,  # 30
        "error": logging.ERROR,  # 40
    }

    logger = logging.getLogger(logger_name)

    if log_level:
        if log_level not in log_levels:
            error_message = (
                "Invalid log_level parameter: {}\n\n"
                "Valid options: debug, info, warning, "
                "warn, error".format(log_level)
            )
            raise Exception(error_message)

        logger.setLevel(log_levels[log_level])
    # Else, NOTSET is Python default.

    logger.propagate = logger.level == logging.NOTSET

    if logger.level != logging.NOTSET and not logger.handlers:
        logger.addHandler(get_stream_handler(format=format, json_logs=json_logs))

        if file_name:
            logger.addHandler(
                get_file_handler(file_name, format=format, json_logs=json_logs)
            )
    # Else if at least one log handler exists that means it has been
    # instantiated with the same name before. Do not keep creating handlers
    # or your logs will be very messy.
    if logger.level == logging.NOTSET:
        # Delete handlers in case level was set back to NOTSET
        # after being set to something else
        del logger.handlers[:]

    return logger


def _get_formatter(
    format: Optional[str], json_logs: Optional[bool]
) -> logging.Formatter:
    """
    Return the formatter for a format and JSON selection.

    Args:
        format (Optional[str]): %-style format string, or None for FORMAT.
        json_logs (Optional[bool]): whether to emit JSON. None defers to the
                                    GEN3_JSON_LOGS env var.

    Returns:
        logging.Formatter: JsonFormatter when JSON is enabled, otherwise a
            TextFormatter over the given template.
    """

    if json_logs is None:
        json_logs = _json_logs_enabled_in_env()

    if json_logs:
        return JsonFormatter()

    return TextFormatter(format or FORMAT)


def _json_logs_enabled_in_env() -> bool:
    """
    Return whether the GEN3_JSON_LOGS env var asks for JSON output.

    Returns:
        bool: True when the env var holds a recognized truthy value.
    """

    return os.environ.get(JSON_LOGS_ENV_VAR, "").strip().lower() in _TRUTHY


def _trace_suffix(record: logging.LogRecord) -> str:
    """
    Build the bracketed trace suffix for a text log line.

    Args:
        record (logging.LogRecord): record to read correlation fields from.

    Returns:
        str: suffix beginning with a space, or an empty string when no trace
            context is available.
    """

    available = [
        "{}={}".format(label, value)
        for label, value in _otel_fields(record).items()
        if value is not None
    ]

    if not available:
        return ""

    return " [{}]".format(" ".join(available))


def _otel_fields(record: logging.LogRecord) -> dict:
    """
    Read OpenTelemetry correlation fields off a record.

    Args:
        record (logging.LogRecord): record to read from.

    Returns:
        dict: correlation field names mapped to their value, or None when the
            field is unavailable.
    """

    return {label: _otel_value(record, attribute) for label, attribute in _OTEL_FIELDS}


def _otel_value(record: logging.LogRecord, attribute: str) -> Optional[str]:
    """
    Read one OpenTelemetry attribute, normalizing "no trace" to None.

    Args:
        record (logging.LogRecord): record to read the value from.
        attribute (str): name of the record attribute holding the value.

    Returns:
        Optional[str]: the value, or None when no trace was recording.
    """

    value = getattr(record, attribute, None)

    # LoggingInstrumentor writes "0" for ids when no span is recording, and an
    # empty service name when unset.
    if not value or (isinstance(value, str) and not value.strip("0")):
        return None

    return value
