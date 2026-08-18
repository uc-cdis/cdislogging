"""tests/test_logging.py

Basic set of tests for logging
"""

import json
import os
import logging
import sys

import pytest

from unittest.mock import MagicMock


import gen3logging


@pytest.fixture(autouse=True)
def delete_loggers():
    """Delete loggers since python logging tries to reuse them"""
    keys = list(logging.Logger.manager.loggerDict.keys())
    for k in keys:
        # Deletes logger object and dict item
        del logging.Logger.manager.loggerDict[k]


@pytest.fixture(autouse=True)
def clear_json_logs_env(monkeypatch):
    """Keep an ambient GEN3_JSON_LOGS out of tests that do not set it."""
    monkeypatch.delenv(gen3logging.JSON_LOGS_ENV_VAR, raising=False)


@pytest.fixture(autouse=True)
def restore_root_logger():
    """Undo root logger changes, which delete_loggers cannot reach."""
    root = logging.getLogger()
    level, handlers = root.level, root.handlers[:]
    yield
    root.handlers[:] = handlers
    root.setLevel(level)


def make_record(**overrides):
    """Build a LogRecord carrying only the attributes a test cares about."""
    attrs = {
        "name": "test_logger",
        "levelname": "INFO",
        "levelno": logging.INFO,
        "msg": "hello world",
    }
    attrs.update(overrides)
    return logging.makeLogRecord(attrs)


def test_get_stream_handler():
    """A stream handler uses the requested plain-text format."""
    handler = gen3logging.get_stream_handler(format=gen3logging.FORMAT)
    assert handler.formatter._fmt == gen3logging.FORMAT


def test_get_file_handler(tmp_path):
    """A file handler opens the named file and uses the requested format."""
    file_name = str(tmp_path / "FAKE-LOGGER.TXT")
    handler = gen3logging.get_file_handler(file_name, format=gen3logging.FORMAT)

    try:
        assert handler.formatter._fmt == gen3logging.FORMAT
        assert handler.stream.name == file_name
        assert os.path.exists(file_name)
    finally:
        handler.close()


def test_json_output_parses_as_json():
    """JSON output is a single parseable object carrying the record's fields."""
    output = gen3logging.JsonFormatter().format(make_record())

    assert "\n" not in output
    parsed = json.loads(output)
    assert parsed["logger"] == "test_logger"
    assert parsed["level"] == "INFO"
    assert parsed["message"] == "hello world"
    assert parsed["timestamp"]


@pytest.mark.parametrize(
    "message",
    [
        'he said "hi"',
        "back\\slash",
        "line one\nline two",
        "tab\there",
        '{"already": "json"}',
        "unicode: ☃",
    ],
)
def test_json_output_escapes_special_characters(message):
    """A message needing JSON escaping round-trips unchanged."""
    output = gen3logging.JsonFormatter().format(make_record(msg=message))

    assert json.loads(output)["message"] == message


def test_json_output_otel_fields_null_when_absent():
    """Trace correlation fields are null when OpenTelemetry is not instrumenting."""
    parsed = json.loads(gen3logging.JsonFormatter().format(make_record()))

    assert parsed["trace_id"] is None
    assert parsed["span_id"] is None
    assert parsed["service"] is None


def test_json_output_otel_fields_populated_when_present():
    """Trace correlation fields are emitted when present on the record."""
    record = make_record(
        otelTraceID="4bf92f3577b34da6a3ce929d0e0e4736",  # pragma: allowlist secret
        otelSpanID="00f067aa0ba902b7",
        otelServiceName="fence",
    )

    parsed = json.loads(gen3logging.JsonFormatter().format(record))
    assert parsed["trace_id"] == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert parsed["span_id"] == "00f067aa0ba902b7"
    assert parsed["service"] == "fence"


@pytest.mark.parametrize(
    "sentinel",
    [
        "0",
        "0" * 16,
        "0" * 32,
        "",
    ],
)
def test_json_output_otel_sentinel_ids_become_null(sentinel):
    """An id meaning "no trace" is emitted as null, not as a sentinel string."""
    record = make_record(otelTraceID=sentinel, otelSpanID=sentinel)

    parsed = json.loads(gen3logging.JsonFormatter().format(record))
    assert parsed["trace_id"] is None
    assert parsed["span_id"] is None


def test_json_output_empty_service_becomes_null():
    """An unset service name is emitted as null rather than an empty string."""
    parsed = json.loads(
        gen3logging.JsonFormatter().format(make_record(otelServiceName=""))
    )

    assert parsed["service"] is None


def test_json_output_keeps_ids_containing_zeros():
    """A real id is preserved even though it contains zero characters."""
    record = make_record(otelSpanID="00f067aa0ba902b7")

    assert json.loads(gen3logging.JsonFormatter().format(record))["span_id"] == (
        "00f067aa0ba902b7"
    )


def test_json_output_interpolates_message_args():
    """Lazy %-style log arguments are interpolated into the message."""
    record = make_record(msg="user %s did %s", args=("alice", "a thing"))

    parsed = json.loads(gen3logging.JsonFormatter().format(record))
    assert parsed["message"] == "user alice did a thing"


def test_json_output_includes_exception():
    """A record with exception info gains an exception field, still valid JSON."""
    try:
        raise ValueError('boom "quoted" and multiline')
    except ValueError:
        record = make_record(exc_info=sys.exc_info())

    parsed = json.loads(gen3logging.JsonFormatter().format(record))
    assert "ValueError" in parsed["exception"]
    assert parsed["message"] == "hello world"


def test_json_output_omits_exception_when_absent():
    """A record without exception info has no exception field."""
    parsed = json.loads(gen3logging.JsonFormatter().format(make_record()))

    assert "exception" not in parsed


def test_default_output_matches_a_plain_legacy_formatter():
    """Default text output is what logging.Formatter(FORMAT) produces."""
    record = make_record()

    assert gen3logging.TextFormatter(gen3logging.FORMAT).format(
        record
    ) == logging.Formatter(gen3logging.FORMAT).format(record)


def test_default_format_emits_text_not_json(capsys):
    """A logger with no format arguments emits legacy text, not JSON."""
    logger = gen3logging.get_logger("text_default", log_level="info")

    logger.info("human readable")

    output = capsys.readouterr().out.strip()
    assert output.endswith("human readable")
    with pytest.raises(json.JSONDecodeError):
        json.loads(output)


def test_text_output_has_no_trace_suffix_without_otel():
    """Text output gains no suffix when no OpenTelemetry fields are present."""
    output = gen3logging.TextFormatter(gen3logging.FORMAT).format(make_record())

    assert output.endswith("hello world")


def test_text_output_appends_trace_suffix():
    """Text output appends trace context when OpenTelemetry supplies it."""
    record = make_record(
        otelTraceID="4bf92f3577b34da6a3ce929d0e0e4736",  # pragma: allowlist secret
        otelSpanID="00f067aa0ba902b7",
        otelServiceName="fence",
    )

    output = gen3logging.TextFormatter(gen3logging.FORMAT).format(record)
    assert output.endswith(
        " [trace_id=4bf92f3577b34da6a3ce929d0e0e4736"
        " span_id=00f067aa0ba902b7 service=fence]"
    )


def test_text_output_omits_unavailable_trace_fields():
    """Only the trace fields that are available appear in the suffix."""
    record = make_record(otelTraceID="0", otelSpanID="0", otelServiceName="fence")

    output = gen3logging.TextFormatter(gen3logging.FORMAT).format(record)
    assert output.endswith(" [service=fence]")


def test_text_output_survives_absent_otel_attributes():
    """Formatting a record with no OpenTelemetry attributes does not raise."""
    record = make_record()

    assert "hello world" in gen3logging.TextFormatter(gen3logging.FORMAT).format(record)


def test_custom_format_also_gets_trace_suffix():
    """A caller-supplied format string still receives the trace suffix."""
    record = make_record(otelServiceName="fence")

    output = gen3logging.TextFormatter("%(levelname)s|%(message)s").format(record)
    assert output == "INFO|hello world [service=fence]"


def test_json_logs_kwarg_enables_json(capsys):
    """json_logs=True switches a logger to JSON output."""
    logger = gen3logging.get_logger("json_kwarg", log_level="info", json_logs=True)

    logger.info('he said "hi"\nand a newline')

    parsed = json.loads(capsys.readouterr().out.strip())
    assert parsed["message"] == 'he said "hi"\nand a newline'
    assert parsed["logger"] == "json_kwarg"


def test_env_var_enables_json(capsys, monkeypatch):
    """GEN3_JSON_LOGS switches output to JSON without a code change."""
    monkeypatch.setenv(gen3logging.JSON_LOGS_ENV_VAR, "true")

    gen3logging.get_logger("json_env", log_level="info").info("via env")

    assert json.loads(capsys.readouterr().out.strip())["message"] == "via env"


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "y", "on", " True "])
def test_env_var_truthy_values(value, monkeypatch):
    """Recognized truthy env values all select JSON."""
    monkeypatch.setenv(gen3logging.JSON_LOGS_ENV_VAR, value)

    handler = gen3logging.get_stream_handler()
    assert isinstance(handler.formatter, gen3logging.JsonFormatter)


@pytest.mark.parametrize("value", ["0", "false", "no", "off", "", "maybe"])
def test_env_var_non_truthy_values(value, monkeypatch):
    """Anything not recognized as truthy leaves output as text."""
    monkeypatch.setenv(gen3logging.JSON_LOGS_ENV_VAR, value)

    handler = gen3logging.get_stream_handler()
    assert isinstance(handler.formatter, gen3logging.TextFormatter)


@pytest.mark.parametrize("json_logs", [True, False])
def test_kwarg_overrides_env_var(json_logs, monkeypatch):
    """An explicit json_logs argument wins over the env var either way."""
    monkeypatch.setenv(gen3logging.JSON_LOGS_ENV_VAR, str(not json_logs).lower())

    handler = gen3logging.get_stream_handler(json_logs=json_logs)
    expected = gen3logging.JsonFormatter if json_logs else gen3logging.TextFormatter
    assert isinstance(handler.formatter, expected)


def test_json_logs_ignores_format_argument():
    """Enabling JSON takes precedence over a supplied text format string."""
    handler = gen3logging.get_stream_handler(format=gen3logging.FORMAT, json_logs=True)

    assert isinstance(handler.formatter, gen3logging.JsonFormatter)


@pytest.mark.parametrize("name", [None, ""])
def test_falsy_name_returns_the_root_logger(name):
    """None and the empty string both configure the root logger."""
    assert gen3logging.get_logger(name, log_level="info") is logging.getLogger()


def test_root_logger_gets_a_handler_when_it_has_none(capsys):
    """A root logger with no handlers yet gets one and emits through it."""
    # pytest's logging plugin attaches its own root handlers, which would
    # otherwise trip the "already instantiated" guard and skip ours.
    logging.getLogger().handlers.clear()

    gen3logging.get_logger(None, log_level="info").info("from root")

    assert capsys.readouterr().out.strip().endswith("from root")


def test_get_logger():
    log_name = "test_get_logger"
    logger = gen3logging.get_logger(log_name)
    assert logger.name == log_name


log_levels = [
    ("debug", logging.DEBUG),
    ("info", logging.INFO),
    ("warning", logging.WARNING),
    ("warn", logging.WARNING),
    ("error", logging.ERROR),
]


@pytest.mark.parametrize("given,expected", log_levels)
def test_get_logger_log_levels(given, expected):
    logger = gen3logging.get_logger(
        "test_get_logger_log_levels" + given, log_level=given
    )
    assert logger.getEffectiveLevel() == expected


def test_multiple_log_handlers():
    logger = gen3logging.get_logger("one_handler", log_level="debug")
    assert len(logger.handlers) == 1

    # make sure it only has one handler associated with the logger name
    logger = gen3logging.get_logger("one_handler", log_level="debug")
    assert len(logger.handlers) == 1


def test_instantiate_with_log_level():
    """
    Check that if logger instantiated with log_level != NOTSET
    then level and propagate are set correctly and handler is created
    """
    logger = gen3logging.get_logger("logger", log_level="info")
    assert logger.level == logging.INFO
    assert logger.propagate == False
    assert len(logger.handlers) == 1


def test_instantiate_without_log_level():
    """
    Check that if logger instantiated without log_level arg
    then level and propagate are set correctly and no handlers created
    """
    logger = gen3logging.get_logger("logger")
    assert logger.level == logging.NOTSET
    assert logger.propagate == True
    assert len(logger.handlers) == 0


def test_log_level():
    """
    Check that logger with level != NOTSET correctly logs according to own level
    """
    logger = gen3logging.get_logger("logger", log_level="info")
    mock_logger_hdlr_emit = MagicMock()
    logger.handlers[0].emit = mock_logger_hdlr_emit

    logger.info("Should emit")
    assert mock_logger_hdlr_emit.call_count == 1

    logger.debug("Should not emit")
    assert mock_logger_hdlr_emit.call_count == 1


def test_log_level_changes():
    """
    Check that logger responds to changes in own log level
    """
    logger = gen3logging.get_logger("logger", log_level="info")
    mock_logger_hdlr_emit = MagicMock()
    logger.handlers[0].emit = mock_logger_hdlr_emit

    logger.debug("Should not emit")
    assert mock_logger_hdlr_emit.call_count == 0

    gen3logging.get_logger("logger", log_level="debug")

    logger.debug("Should now emit")
    assert mock_logger_hdlr_emit.call_count == 1


def test_child_inherits_parent_level():
    """
    Check that child logger with level NOTSET will log according to parent level
    """
    parent = gen3logging.get_logger("parent", log_level="info")
    mock_parent_hdlr_emit = MagicMock()
    parent.handlers[0].emit = mock_parent_hdlr_emit

    child = gen3logging.get_logger("parent.child")  # No handlers

    child.info("Should emit via parent")
    assert mock_parent_hdlr_emit.call_count == 1
    child.debug("Should not emit since parent level is info and child level is notset")
    assert mock_parent_hdlr_emit.call_count == 1


def test_child_inherits_parent_level_changes():
    """
    Check that child logger with level NOTSET will respond to changes in parent log level
    """
    parent = gen3logging.get_logger("parent", log_level="info")
    mock_parent_hdlr_emit = MagicMock()
    parent.handlers[0].emit = mock_parent_hdlr_emit

    child = gen3logging.get_logger("parent.child")  # No handlers

    child.debug("should not emit since parent level is info")
    assert mock_parent_hdlr_emit.call_count == 0

    gen3logging.get_logger("parent", log_level="debug")

    child.debug("should now emit")
    assert mock_parent_hdlr_emit.call_count == 1


def test_child_change_level_from_notset_updates_properties():
    """
    Check that if a child logger was instantiated with level NOTSET
    and then get_logger() is called on it with a log_level arg != 'notset',
    the child logger correctly updates level and propagate,
    and gets its own handler
    """
    parent = gen3logging.get_logger("parent", log_level="info")
    child = gen3logging.get_logger("parent.child")
    assert child.propagate == True
    assert len(child.handlers) == 0

    # TODO: should really rename this to get_or_update_logger...
    gen3logging.get_logger("parent.child", log_level="warn")

    assert child.propagate == False
    assert len(child.handlers) == 1


def test_child_change_level_from_notset_logs_own_level():
    """
    Check that if a child logger was instantiated with level NOTSET
    and then get_logger() is called on it with a log_level arg != 'notset',
    the child logger correctly logs at its own new level
    on its own new handler
    """
    parent = gen3logging.get_logger("parent", log_level="info")
    mock_parent_hdlr_emit = MagicMock()
    parent.handlers[0].emit = mock_parent_hdlr_emit

    child = gen3logging.get_logger("parent.child")

    gen3logging.get_logger("parent.child", log_level="warn")
    mock_child_hdlr_emit = MagicMock()
    child.handlers[0].emit = mock_child_hdlr_emit

    child.warning(
        "Should emit with child hdlr only; child no longer inherits/propagates"
    )
    assert mock_parent_hdlr_emit.call_count == 0
    assert mock_child_hdlr_emit.call_count == 1

    child.info("Should not emit; child level is now warn")
    assert mock_parent_hdlr_emit.call_count == 0
    assert mock_child_hdlr_emit.call_count == 1


def test_reset_to_notset():
    """
    Check that if logger was instantiated with log_level != NOTSET
    and then get_logger() is called on it again with log_level='notset',
    the logger's log level is correctly reset to NOTSET
    and the logger logs at the correct level
    """
    parent = gen3logging.get_logger("parent", log_level="debug")
    mock_parent_hdlr_emit = MagicMock()
    parent.handlers[0].emit = mock_parent_hdlr_emit

    child = gen3logging.get_logger("parent.child", log_level="info")
    mock_child_hdlr_emit = MagicMock()
    child.handlers[0].emit = mock_child_hdlr_emit

    child = gen3logging.get_logger("parent.child", log_level="notset")
    assert child.propagate == True
    assert len(child.handlers) == 0

    child.info("Should emit with parent hdlr only")
    assert mock_parent_hdlr_emit.call_count == 1
    assert mock_child_hdlr_emit.call_count == 0

    child.debug("Should emit with parent hdlr only")
    assert mock_parent_hdlr_emit.call_count == 2
    assert mock_child_hdlr_emit.call_count == 0


def test_no_unintentional_reset_to_notset():
    """
    Check that if logger was instantiated with log_level != NOTSET
    and then get_logger() is called on it again without a log_level arg,
    the logger's log level does _not_ get reset to NOTSET
    """
    parent = gen3logging.get_logger("parent", log_level="debug")
    mock_parent_hdlr_emit = MagicMock()
    parent.handlers[0].emit = mock_parent_hdlr_emit

    child = gen3logging.get_logger("parent.child", log_level="info")
    mock_child_hdlr_emit = MagicMock()
    child.handlers[0].emit = mock_child_hdlr_emit

    child.info("Sanity check that this will emit on child hdlr")
    assert mock_parent_hdlr_emit.call_count == 0
    assert mock_child_hdlr_emit.call_count == 1

    child = gen3logging.get_logger("parent.child")
    child.debug(
        "Should not emit, but will emit on parent hdlr if child level was reset to NOTSET"
    )

    assert mock_parent_hdlr_emit.call_count == 0
    assert mock_child_hdlr_emit.call_count == 1
