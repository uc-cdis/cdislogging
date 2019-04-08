# cdislogging
Logging routines to centralize format

Basic usage:
---

In the parent/root module:
```python
from cdislogging import get_logger

logger = get_logger('__name__', log_level='info')
logger.info('Hello world!')
```
In a child module:
```python
from cdislogging import get_logger

logger = get_logger('__name__')
logger.info('Hello world!')

logger = get_logger('__name__', log_level='debug')
logger.debug('I am a child logger but I now have my own custom log level!')
```

You _must_ set the logging level on the parent logger!

The default `log_level` argument in `get_logger` is `NONE`, which means the default logging level for new loggers is `NOTSET`. This means that child loggers whose levels were not explicitly set will inherit logging levels and handlers from ancestor loggers. This makes it easier to do things like change application-wide logging levels by just setting the level on the parent logger. Levels and handlers can still be individually set on child nodes by providing a `log_level` argument.

See more about Python logging [here](https://docs.python.org/3/library/logging.html).

Optional parameters:
---

* file_name (default: None) - If present, the logger will output logs to a file as well as stdout
* log_level (default: 'debug') - Change the log level
