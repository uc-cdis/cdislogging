"""Basic set of tests for logging"""

import logging
import os
from unittest.mock import MagicMock

import pytest  # pylint: disable=E0401

import cdislogging


@pytest.fixture(autouse=True)
def delete_loggers():
    """Delete loggers since python logging tries to reuse them"""
    keys = list(logging.Logger.manager.loggerDict.keys())
    for k in keys:
        # Deletes logger object and dict item
        del logging.Logger.manager.loggerDict[k]


def test_get_stream_handler():
    """Test get_stream_handler"""
    handler = cdislogging.get_stream_handler()
    assert (
        handler.formatter._fmt == cdislogging.FORMAT  # pylint: disable=protected-access
    )


def test_get_file_handler():
    """Test get_file_handler"""
    file_name = "FAKE-LOGGER.TXT"
    handler = cdislogging.get_file_handler(file_name)
    assert (
        handler.formatter._fmt == cdislogging.FORMAT  # pylint: disable=protected-access
    )
    assert os.path.basename(handler.stream.name) == file_name
    assert os.path.exists(file_name)

    # cleanup
    if os.path.exists(file_name):
        os.remove(file_name)


def test_get_logger():
    """Test get_logger"""
    log_name = "test_get_logger"
    logger = cdislogging.get_logger(log_name)
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
    """Test get_logger_log_levels"""
    logger = cdislogging.get_logger(
        "test_get_logger_log_levels" + given, log_level=given
    )
    assert logger.getEffectiveLevel() == expected


def test_multiple_log_handlers():
    """Test multiple log handlers"""
    logger = cdislogging.get_logger("one_handler", log_level="debug")
    assert len(logger.handlers) == 1

    # make sure it only has one handler associated with the logger name
    logger = cdislogging.get_logger("one_handler", log_level="debug")
    assert len(logger.handlers) == 1


def test_instantiate_with_log_level():
    """
    Check that if logger instantiated with log_level != NOTSET
    then level and propagate are set correctly and handler is created
    """
    logger = cdislogging.get_logger("logger", log_level="info")
    assert logger.level == logging.INFO
    assert logger.propagate is False
    assert len(logger.handlers) == 1


def test_instantiate_without_log_level():
    """
    Check that if logger instantiated without log_level arg
    then level and propagate are set correctly and no handlers created
    """
    logger = cdislogging.get_logger("logger")
    assert logger.level == logging.NOTSET
    assert logger.propagate is True
    assert len(logger.handlers) == 0


def test_log_level():
    """
    Check that logger with level != NOTSET correctly logs according to own level
    """
    logger = cdislogging.get_logger("logger", log_level="info")
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
    logger = cdislogging.get_logger("logger", log_level="info")
    mock_logger_hdlr_emit = MagicMock()
    logger.handlers[0].emit = mock_logger_hdlr_emit

    logger.debug("Should not emit")
    assert mock_logger_hdlr_emit.call_count == 0

    cdislogging.get_logger("logger", log_level="debug")

    logger.debug("Should now emit")
    assert mock_logger_hdlr_emit.call_count == 1


def test_child_inherits_parent_level():
    """
    Check that child logger with level NOTSET will log according to parent level
    """
    parent = cdislogging.get_logger("parent", log_level="info")
    mock_parent_hdlr_emit = MagicMock()
    parent.handlers[0].emit = mock_parent_hdlr_emit

    child = cdislogging.get_logger("parent.child")  # No handlers

    child.info("Should emit via parent")
    assert mock_parent_hdlr_emit.call_count == 1
    child.debug("Should not emit since parent level is info and child level is notset")
    assert mock_parent_hdlr_emit.call_count == 1


def test_child_inherits_parent_level_changes():
    """
    Check that child logger with level NOTSET will respond to changes in parent log level
    """
    parent = cdislogging.get_logger("parent", log_level="info")
    mock_parent_hdlr_emit = MagicMock()
    parent.handlers[0].emit = mock_parent_hdlr_emit

    child = cdislogging.get_logger("parent.child")  # No handlers

    child.debug("should not emit since parent level is info")
    assert mock_parent_hdlr_emit.call_count == 0

    cdislogging.get_logger("parent", log_level="debug")

    child.debug("should now emit")
    assert mock_parent_hdlr_emit.call_count == 1


def test_child_change_level_from_notset_updates_properties():
    """
    Check that if a child logger was instantiated with level NOTSET
    and then get_logger() is called on it with a log_level arg != 'notset',
    the child logger correctly updates level and propagate,
    and gets its own handler
    """
    child = cdislogging.get_logger("parent.child")
    assert child.propagate is True
    assert len(child.handlers) == 0

    # TODO: should really rename this to get_or_update_logger...
    cdislogging.get_logger("parent.child", log_level="warn")

    assert child.propagate is False
    assert len(child.handlers) == 1


def test_child_change_level_from_notset_logs_own_level():
    """
    Check that if a child logger was instantiated with level NOTSET
    and then get_logger() is called on it with a log_level arg != 'notset',
    the child logger correctly logs at its own new level
    on its own new handler
    """
    parent = cdislogging.get_logger("parent", log_level="info")
    mock_parent_hdlr_emit = MagicMock()
    parent.handlers[0].emit = mock_parent_hdlr_emit

    child = cdislogging.get_logger("parent.child")

    cdislogging.get_logger("parent.child", log_level="warn")
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


def test_no_reset_and_reset_to_notset():
    """
    Check that if logger was instantiated with log_level != NOTSET
    and then get_logger() is called on it again without a log_level arg,
    the logger's log level does _not_ get reset to NOTSET

    Then check if get_logger() is called on it again with log_level='notset',
    the logger's log level is correctly reset to NOTSET
    and the logger logs at the correct level
    """
    parent = cdislogging.get_logger("parent", log_level="debug")
    mock_parent_hdlr_emit = MagicMock()
    parent.handlers[0].emit = mock_parent_hdlr_emit

    child = cdislogging.get_logger("parent.child", log_level="info")
    mock_child_hdlr_emit = MagicMock()
    child.handlers[0].emit = mock_child_hdlr_emit

    child.info("Sanity check that this will emit on child hdlr")
    assert mock_parent_hdlr_emit.call_count == 0
    assert mock_child_hdlr_emit.call_count == 1

    # get_logger() is called on it again without a log_level arg,
    child = cdislogging.get_logger("parent.child")
    child.debug(
        "Should not emit, but will emit on parent hdlr if child level was reset to NOTSET"
    )
    # the logger's log level does _not_ get reset to NOTSET
    assert mock_parent_hdlr_emit.call_count == 0
    assert mock_child_hdlr_emit.call_count == 1

    # get_logger() is called on it again with log_level='notset',
    child = cdislogging.get_logger("parent.child", log_level="notset")
    assert child.propagate is True
    assert len(child.handlers) == 0

    # the logger's log level is correctly reset to NOTSET
    # and the logger logs at the correct level (ie, parent)
    child.info("Should emit with parent hdlr only")
    assert mock_parent_hdlr_emit.call_count == 1
    assert mock_child_hdlr_emit.call_count == 1

    child.debug("Should emit with parent hdlr only")
    assert mock_parent_hdlr_emit.call_count == 2
    assert mock_child_hdlr_emit.call_count == 1
