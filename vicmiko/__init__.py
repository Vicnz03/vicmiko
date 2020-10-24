import logging

# Logging configuration
log = logging.getLogger(__name__)  
log.addHandler(logging.NullHandler())

__version__ = "0.0.3"