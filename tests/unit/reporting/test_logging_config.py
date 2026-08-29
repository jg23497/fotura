import logging

from fotura.reporting.logging_config import OAUTH_FLOW_LOGGER, setup_logging


def test_setup_logging_suppresses_google_oauth_logs_below_warning():
    oauth_logger = logging.getLogger(OAUTH_FLOW_LOGGER)
    root_logger = logging.getLogger()
    original_level = oauth_logger.level
    original_handlers = list(root_logger.handlers)

    try:
        setup_logging()

        assert not oauth_logger.isEnabledFor(logging.INFO)
        assert oauth_logger.isEnabledFor(logging.WARNING)
    finally:
        oauth_logger.setLevel(original_level)
        for handler in root_logger.handlers:
            if handler not in original_handlers:
                root_logger.removeHandler(handler)
