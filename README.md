# gen3logging

Logging routines to centralize format.

## Basic usage

---

In the parent/root module:

```python
from gen3logging import get_logger

logger = get_logger("{{service_name}}", log_level='info')
logger.info('Hello world!')
```

In a child module:

```python
from gen3logging import get_logger

logger = get_logger(__name__)
logger.info('Hello world!')

logger = get_logger(__name__, log_level='debug')
logger.debug('I am a child logger but I now have my own custom log level!')
```

You _must_ set the logging level on the parent logger!

Inheritance is by dotted name, so the root logger's name must be a prefix of the
child module's `__name__`. Naming the root after the top-level package (a module
in `fence/auth.py` has `__name__ == "fence.auth"`, which inherits from `fence`)
is what makes this work. A root name that is not a prefix of its modules' names
gets no children.

The default `log_level` argument in `get_logger` is `None`, which means the default logging level for new loggers is `NOTSET`. This means that child loggers whose levels were not explicitly set will inherit logging levels and handlers from ancestor loggers. This makes it easier to do things like change application-wide logging levels by just setting the level on the parent logger. Levels and handlers can still be individually set on child nodes by providing a `log_level` argument.

See more about Python logging [here](https://docs.python.org/3/library/logging.html).

## Output format

---

By default logs are plain text:

```
[2025-01-15 12:22:04,031][      fence][   INFO] user logged in
```

When OpenTelemetry is active, trace context is appended automatically:

```
[2025-01-15 12:22:04,031][      fence][   INFO] user logged in [trace_id=4bf92f3577b34da6a3ce929d0e0e4736 span_id=00f067aa0ba902b7 service=fence]
```

The suffix carries only the fields that are available, and is absent entirely
when none are. `gen3logging` does not depend on OpenTelemetry: populate these by
installing `opentelemetry-instrumentation-logging` and calling
`LoggingInstrumentor().instrument()`. Nothing needs to change here to pick them
up, and nothing fails when they are missing.

`trace_id` and `span_id` are either a usable id or absent.


Any `%`-style format string can replace the default:

```python
logger = get_logger("gen3foo", log_level='info', format="%(levelname)s %(message)s")
```

## Enabling JSON Logs

---

Set `json_logs=True` to emit one JSON object per line instead of the default format:

```python
logger = get_logger("gen3foo", log_level='info', json_logs=True)
```

```json
{"timestamp": "2025-01-15T18:22:04.031Z", "logger": "fence.auth", "level": "INFO", "message": "user logged in", "trace_id": null, "span_id": null, "service": null}
```

| Key                              | Value                                                             |
| -------------------------------- | ----------------------------------------------------------------- |
| `timestamp`                      | ISO 8601 UTC, millisecond precision                               |
| `logger`                         | logger name                                                       |
| `level`                          | level name, e.g. `INFO`                                           |
| `message`                        | the formatted message, with `%`-style arguments interpolated      |
| `trace_id`, `span_id`, `service` | OpenTelemetry correlation, `null` when unavailable                |
| `exception`                      | traceback text, present only on records that carry exception info |

Because the message and traceback are JSON-escaped, a multi-line traceback stays
on a single log line and can be parsed by a log aggregator without stitching.

To turn JSON on for a deployment without a code change, set the
`GEN3_JSON_LOGS` environment variable:

```
GEN3_JSON_LOGS=true
```

An explicit `json_logs` argument always wins over the environment variable, so a
service can force either format. When `json_logs` is omitted the environment
variable decides, and when neither is set, output is text. Enabling JSON
supersedes any `format` string.

## Migrating from `cdislogging`

---

1. Replace the `cdislogging` dependency with `gen3logging>=2.0.0`.
2. Replace `from cdislogging import ...` with `from gen3logging import ...`.

That is the whole migration. Output is identical to `cdislogging` 1.2.0
until you enable JSON or instrument with OpenTelemetry.
