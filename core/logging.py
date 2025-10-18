import logging
import logging.config
import os
from pythonjsonlogger import jsonlogger


def setup_logging(log_dir: str = "logs"):
    os.makedirs(log_dir, exist_ok=True)

    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {"format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"},
            "json": {
                "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
                "fmt": "%(asctime)s %(levelname)s %(name)s %(message)s %(pathname)s %(lineno)d",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "standard",
                "level": "DEBUG",
            },
            "file": {
                "class": "logging.handlers.RotatingFileHandler",
                "formatter": "json",
                "filename": os.path.join(log_dir, "app.log"),
                "maxBytes": 5 * 1024 * 1024,
                "backupCount": 5,
                "level": "INFO",
                "encoding": "utf-8",
            },
        },
        "root": {
            "handlers": ["console", "file"],
            "level": "INFO",
        },
        "loggers": {
            "core": {
                "handlers": ["console", "file"],
                "level": "DEBUG",
                "propagate": False,
            },
        },
    }

    logging.config.dictConfig(logging_config)
    return logging.getLogger("core")
