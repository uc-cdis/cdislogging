"""
Logging with a standardized format
"""

import json
import logging
import os
import sys
import time
from types import MappingProxyType
from typing import TextIO

FORMAT = "[%(asctime)s][%(name)10s][%(levelname)7s] %(message)s"

JSON_LOGS_ENV_VAR = "GEN3_JSON_LOGS"

_TRUTHY = frozenset({"1", "true", "t", "yes", "y", "on"})

_LOG_LEVELS = MappingProxyType(
    {
        "notset": logging.NOTSET,
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "warn": logging.WARNING,
        "error": logging.ERROR,
        "critical": logging.CRITICAL,
    }
)

_TRACE_SUFFIX_ATTRIBUTE = "gen3_trace_suffix"

_OTEL_ATTRIBUTES = (
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

    def __init__(self, fmt: str, datefmt: str | None = None) -> None:
        """
        Build a formatter whose template ends with the trace suffix.

        The suffix must stay a template field: format appends any traceback
        and stack after the template, so this is what keeps the suffix on the
        message line.

        Args:
            fmt (str): %-style format string.
            datefmt (str | None): strftime format for asctime, or None for the
                                     logging default.
        """

        super().__init__(fmt + "%(" + _TRACE_SUFFIX_ATTRIBUTE + ")s", datefmt)

    def format(self, record: logging.LogRecord) -> str:
        """
        Render a record as text, with a trace suffix when one is available.

        Args:
            record (logging.LogRecord): record to format.

        Returns:
            str: the formatted line, followed by any traceback or stack.
        """

        setattr(record, _TRACE_SUFFIX_ATTRIBUTE, _trace_suffix(record))

        return super().format(record)


class JsonFormatter(logging.Formatter):
    """
    Format log records as single-line JSON objects.

    OpenTelemetry correlation fields are read off the record when present and
    emitted as null otherwise, so records format correctly whether or not
    opentelemetry-instrumentation-logging is installed and instrumenting.

    Fields passed through a logging call's `extra=` are not emitted.
    """

    # gmtime pairs with the trailing Z in default_msec_format; localtime would
    # label local times as UTC. staticmethod is for type checkers, which treat a
    # bare callable class attribute as an unbound method and reject it as an
    # incompatible override of Formatter.converter.
    converter = staticmethod(time.gmtime)
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
    format: str | None = None, json_logs: bool | None = None
) -> logging.StreamHandler[TextIO]:
    """
    Return a stdout stream handler

    All logs will write to stdout.

    Args:
        format (str | None): %-style format string. Defaults to
                                FORMAT. Ignored when JSON is enabled.
        json_logs (bool | None): emit JSON instead of text. When None, falls
                                    back to the GEN3_JSON_LOGS env var.

    Returns:
        logging.StreamHandler[TextIO]: pre-formatted stream handler
    """

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_get_formatter(format, json_logs))

    return handler


def get_file_handler(
    file_name: str, format: str | None = None, json_logs: bool | None = None
) -> logging.FileHandler:
    """
    Return a file handler

    Args:
        file_name (str): name of file to write logs to
        format (str | None): %-style format string. Defaults to
                                FORMAT. Ignored when JSON is enabled.
        json_logs (bool | None): emit JSON instead of text. When None, falls
                                    back to the GEN3_JSON_LOGS env var.

    Returns:
        logging.FileHandler: pre-formatted file handler
    """

    handler = logging.FileHandler(file_name)
    handler.setFormatter(_get_formatter(format, json_logs))

    return handler


def get_logger(
    logger_name: str | None,
    file_name: str | None = None,
    log_level: str | None = None,
    format: str | None = None,
    json_logs: bool | None = None,
) -> logging.Logger:
    """
    Return an opinionated basic logger named `logger_name` that logs to stdout

    If you leave the log level argument as None and the logger was not
    previously instantiated, the level will be set to NOTSET. If the logger
    was previously instantiated, the level will be left alone.

    If the level is NOTSET, then ancestor loggers are traversed and searched
    for a log_level and handler. See python docs.

    If you change the log level to something other than debug (or notset) then it will not
    display log statements below that level (see example below for details).
    Ideally this should be handled by your application's command line args.

    file_name, format and json_logs only apply when the logger gets its
    handlers, which happens on the first call that sets a level other than
    notset. A later call for the same logger leaves its handlers as they are,
    so GEN3_JSON_LOGS is the reliable way to switch a whole service to JSON.

    eg:
    ```
    log = get_logger('hi', log_level='info')
    log.debug('hello world') # <- this will not display
    ```

    Args:
        logger_name (str | None): name of the logger, or None for the root logger.
                                     Python's root logger defaults to WARNING, so it
                                     gets a handler even without a log_level, and
                                     log_level="notset" removes every root handler,
                                     including ones other libraries installed.
        file_name (str | None): if present, will write logs to file as well
        log_level (str | None): level of logging for this logger, in any case. string
                                   so you don't have to import logging in the
                                   application
        format (str | None): %-style format string. Defaults to
                                FORMAT. Ignored when JSON is enabled.
        json_logs (bool | None): emit JSON instead of text. When None, falls
                                    back to the GEN3_JSON_LOGS env var.

    Returns:
        logging.Logger: pre-formatted logger object

    Raises:
        ValueError: if log_level is not one of the supported level names.
    """

    logger = logging.getLogger(logger_name)

    if log_level:
        # notset maps to 0, so a falsiness check would reject it
        level = _LOG_LEVELS.get(log_level.lower())
        if level is None:
            raise ValueError(
                f"Invalid log_level parameter: {log_level}. "
                f"Valid options: {', '.join(_LOG_LEVELS)}"
            )

        logger.setLevel(level)
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


def _get_formatter(format: str | None, json_logs: bool | None) -> logging.Formatter:
    """
    Return the formatter for a format and JSON selection.

    Args:
        format (str | None): %-style format string, or None for FORMAT.
        json_logs (bool | None): whether to emit JSON. None defers to the
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


def _otel_fields(record: logging.LogRecord) -> dict[str, str | None]:
    """
    Read OpenTelemetry correlation fields off a record.

    Args:
        record (logging.LogRecord): record to read from.

    Returns:
        dict[str, str | None]: correlation field names mapped to their value,
            or None when the field is unavailable.
    """

    return {
        label: _otel_value(record, attribute) for label, attribute in _OTEL_ATTRIBUTES
    }


def _otel_value(record: logging.LogRecord, attribute: str) -> str | None:
    """
    Read one OpenTelemetry attribute, normalizing "no trace" to None.

    Args:
        record (logging.LogRecord): record to read the value from.
        attribute (str): name of the record attribute holding the value.

    Returns:
        str | None: the value, or None when no trace was recording.
    """

    value = getattr(record, attribute, None)

    # LoggingInstrumentor writes "0" for ids when no span is recording, and an
    # empty service name when unset.
    if not value or (isinstance(value, str) and not value.strip("0")):
        return None

    return value
