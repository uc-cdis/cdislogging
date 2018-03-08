"""cdislogging

Logging with a standardized format
"""

import logging
import sys


FORMAT = '[%(asctime)s][%(name)10s][%(levelname)7s] %(message)s'

def get_stream_handler():
    """Return a stdout stream handler

    All logs will write to stdout.

    Return:
        logging.StreamHandler: pre-formatted file handler
    """

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(FORMAT))

    return handler

def get_file_handler(file_name):
    """Return a file handler

    Args:
        file_name (string): name of file to write logs to

    Return:
        logging.FileHandler: pre-formatted stream handler
    """

    handler = logging.FileHandler(file_name)
    handler.setFormatter(logging.Formatter(FORMAT))

    return handler

def get_logger(logger_name, file_name=None, log_level='debug'):
    """Return an opinionated basic logger named `name` that logs to stdout

    If you change the log level to something other than debug then it will not
    display log statements below that level (see example and chart below for details).
    Ideally this should be handled by your application's command line args.

    eg:
    ```
    log = get_logger('hi', log_level='info')
    log.debug('hello world') # <- this will not display
    ```

    Args:
        logger_name (string): name of the logger
        file_name (string): if present, will write logs to file as well
        log_level (string): level of logging for this logger. string so you
                            don't have to import logging in the application

    Return:
        logging.Logger: pre-formatted logger object
    """

    log_levels = {                  # sorted level
        'debug': logging.DEBUG,     # 10
        'info': logging.INFO,       # 20
        'warning': logging.WARNING, # 30
        'warn': logging.WARNING,    # 30
        'error': logging.ERROR,     # 40
    }

    if log_level not in log_levels:
        error_message = 'Invalid log_level parameter: {}\n\n' \
                        'Valid options: debug, info, warning, ' \
                        'warn, error'.format(log_level)
        raise Exception(error_message)

    logger = logging.getLogger(logger_name)

    # If at least one log handler exists that means it has been
    # instantiated with the same name before. Do not keep creating handlers
    # or your logs will be very messy.
    if logger.handlers:
        return logger

    logger.setLevel(log_levels[log_level])
    logger.addHandler(get_stream_handler())

    if file_name:
        logger.addHandler(get_file_handler(file_name))

    logger.propagate = False
    return logger
