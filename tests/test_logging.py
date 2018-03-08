"""tests/test_logging.py

Basic set of tests for logging
"""

import os
import logging

import pytest

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
