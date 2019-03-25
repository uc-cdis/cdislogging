"""tests/test_logging.py

Basic set of tests for logging
"""

import os
import logging

import pytest

# Python 2 and 3 compatible
try:
    from unittest.mock import MagicMock
    from unittest.mock import patch
except ImportError:
    from mock import MagicMock
    from mock import patch

import cdislogging

def test_get_stream_handler():
    handler = cdislogging.get_stream_handler()
    assert handler.formatter._fmt == cdislogging.FORMAT

def test_get_file_handler():
    file_name = 'FAKE-LOGGER.TXT'
    handler = cdislogging.get_file_handler(file_name)
    assert handler.formatter._fmt == cdislogging.FORMAT
    assert os.path.basename(handler.stream.name) == file_name
    assert os.path.exists(file_name)

    # cleanup
    if os.path.exists(file_name):
        os.remove(file_name)

def test_get_logger():
    log_name = 'test_get_logger'
    logger = cdislogging.get_logger(log_name)
    assert logger.name == log_name

log_levels = [
    ('debug', logging.DEBUG),
    ('info', logging.INFO),
    ('warning', logging.WARNING),
    ('warn', logging.WARNING),
    ('error', logging.ERROR),
]
@pytest.mark.parametrize("given,expected", log_levels)
def test_get_logger_log_levels(given, expected):
    logger = cdislogging.get_logger('test_get_logger_log_levels' + given, log_level=given)
    assert logger.getEffectiveLevel() == expected

def test_multiple_log_handlers():
    logger = cdislogging.get_logger('one_handler', log_level='debug')
    assert len(logger.handlers) == 1

    # make sure it only has one handler associated with the logger name
    logger = cdislogging.get_logger('one_handler', log_level='debug')
    assert len(logger.handlers) == 1

def test_inheritance():
    parent = cdislogging.get_logger('parent', log_level='info')
    assert parent.propagate == False
    assert len(parent.handlers) == 1

    child = cdislogging.get_logger('parent.child')
    assert child.propagate == True
    assert len(child.handlers) == 0

    mock_parent_hdlr = MagicMock()
    parent.handlers[0].emit = mock_parent_hdlr

    child.info("Should emit")
    assert mock_parent_hdlr.call_count == 1
    child.debug("Should not emit")
    assert mock_parent_hdlr.call_count == 1

    parent = cdislogging.get_logger('parent', log_level='debug')

    child.info("Should emit")
    assert mock_parent_hdlr.call_count == 2
    child.debug("Should emit")
    assert mock_parent_hdlr.call_count == 3

    child = cdislogging.get_logger('parent.child', log_level='warn')
    assert child.propagate == False
    assert len(child.handlers) == 1

    mock_child_hdlr = MagicMock()
    child.handlers[0].emit = mock_child_hdlr

    parent.warn("Should emit with parent hdlr")
    assert mock_parent_hdlr.call_count == 4
    assert mock_child_hdlr.call_count == 0

    child.info("Should not emit at all")
    assert mock_parent_hdlr.call_count == 4
    assert mock_child_hdlr.call_count == 0

    child.warn("Should emit with child hdlr only")
    assert mock_parent_hdlr.call_count == 4
    assert mock_child_hdlr.call_count == 1

    child = cdislogging.get_logger('parent.child', log_level='notset')
    assert child.propagate == True
    assert len(child.handlers) == 0

    child.info("Should emit with parent hdlr only")
    assert mock_parent_hdlr.call_count == 5
    assert mock_child_hdlr.call_count == 1
