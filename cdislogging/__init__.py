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

def get_logger(logger_name, file_name=None, log_level=None):
    """Return an opinionated basic logger named `name` that logs to stdout

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
        logger_name (string): name of the logger
        file_name (string): if present, will write logs to file as well
        log_level (string): level of logging for this logger. string so you
                            don't have to import logging in the application

    Return:
        logging.Logger: pre-formatted logger object
    """

    log_levels = {                  # sorted level
        'notset': logging.NOTSET,   # 00
        'debug': logging.DEBUG,     # 10
        'info': logging.INFO,       # 20
        'warning': logging.WARNING, # 30
        'warn': logging.WARNING,    # 30
        'error': logging.ERROR,     # 40
    }

    logger = logging.getLogger(logger_name)

    if log_level:
        if log_level not in log_levels:
            error_message = 'Invalid log_level parameter: {}\n\n' \
                            'Valid options: debug, info, warning, ' \
                            'warn, error'.format(log_level)
            raise Exception(error_message)

        logger.setLevel(log_levels[log_level])
    # Else, NOTSET is Python default.

    logger.propagate = logger.level == logging.NOTSET

    if logger.level != logging.NOTSET and not logger.handlers:
        logger.addHandler(get_stream_handler())

        if file_name:
            logger.addHandler(get_file_handler(file_name))
    # Else if at least one log handler exists that means it has been
    # instantiated with the same name before. Do not keep creating handlers
    # or your logs will be very messy.
    if logger.level == logging.NOTSET:
        # Delete handlers in case level was set back to NOTSET
        # after being set to something else
        del logger.handlers[:]

    return logger
