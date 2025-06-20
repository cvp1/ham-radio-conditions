"""
Logging configuration for Ham Radio Conditions app.
Provides consistent logging setup across the application.
"""

import logging
import logging.handlers
import os
from typing import Optional
from config import get_config


def setup_logging(
    name: str = __name__,
    level: Optional[str] = None,
    log_file: Optional[str] = None
) -> logging.Logger:
    """
    Set up logging configuration.
    
    Args:
        name: Logger name
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional log file path
    
    Returns:
        Configured logger instance
    """
    config = get_config()
    
    # Determine log level
    if level is None:
        level = 'DEBUG' if config.DEBUG else 'INFO'
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # Clear existing handlers
    logger.handlers.clear()
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, level.upper()))
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler (if log_file is specified)
    if log_file:
        # Ensure log directory exists
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
        
        # Create rotating file handler
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(getattr(logging, level.upper()))
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


def get_logger(name: str = __name__) -> logging.Logger:
    """
    Get a logger instance with default configuration.
    
    Args:
        name: Logger name
    
    Returns:
        Logger instance
    """
    config = get_config()
    
    # Set up logging if not already configured
    if not logging.getLogger(name).handlers:
        log_file = None
        if config.is_production():
            log_file = 'logs/ham_radio_conditions.log'
        
        setup_logging(name, log_file=log_file)
    
    return logging.getLogger(name)


# Create default logger
logger = get_logger(__name__) 