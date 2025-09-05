"""
Centralized logging configuration for MirCrew Indexer.

This module provides centralized logging configuration with support for
YAML-based or programmatic configuration. It can override logging levels
through environment variables.
"""

import logging
import logging.config
import os
from pathlib import Path
from typing import Optional, Union, Dict, Any
import sys


def _load_yaml_config(config_path: str) -> Optional[Dict[str, Any]]:
    """Load YAML logging configuration with fallback."""
    try:
        import yaml
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                return config if isinstance(config, dict) else None
        except (FileNotFoundError, yaml.YAMLError):
            return None
    except ImportError:
        return None


def _get_default_config() -> Dict[str, Any]:
    """Get default logging configuration when YAML is not available."""
    return {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'simple': {
                'format': '%(levelname)s: %(message)s'
            }
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'level': 'DEBUG',
                'formatter': 'simple',
                'stream': sys.stdout
            }
        },
        'loggers': {
            'mircrew': {
                'level': 'INFO',
                'handlers': ['console'],
                'propagate': False
            },
            'mircrew.api': {
                'level': 'INFO',
                'handlers': ['console'],
                'propagate': False
            },
            'mircrew.core': {
                'level': 'INFO',
                'handlers': ['console'],
                'propagate': False
            },
            'mircrew.utils': {
                'level': 'INFO',
                'handlers': ['console'],
                'propagate': False
            }
        },
        'root': {
            'level': 'INFO',
            'handlers': ['console']
        }
    }


def _apply_env_overrides(config: Dict[str, Any]) -> Dict[str, Any]:
    """Apply environment variable overrides to logging configuration."""
    # Override root log level
    env_level = os.getenv('LOG_LEVEL')
    if env_level:
        config['root']['level'] = env_level.upper()

    # Override specific logger levels
    for logger_name in config.get('loggers', {}):
        env_key = f"LOG_LEVEL_{logger_name.replace('.', '_').replace('-', '_').upper()}"
        env_value = os.getenv(env_key)
        if env_value:
            config['loggers'][logger_name]['level'] = env_value.upper()

    # Add file handler if LOG_FILE is specified
    log_file = os.getenv('LOG_FILE')
    if log_file:
        config['handlers']['file'] = {
            'class': 'logging.FileHandler',
            'level': 'INFO',
            'formatter': 'simple',
            'filename': log_file,
            'encoding': 'utf-8'
        }

        # Add file handler to all loggers
        for logger_name in config.get('loggers', {}):
            if 'file' not in config['loggers'][logger_name]['handlers']:
                config['loggers'][logger_name]['handlers'].append('file')
        if 'file' not in config['root']['handlers']:
            config['root']['handlers'].append('file')

    return config


def setup_logging(config_path: Optional[Union[str, Path]] = None, use_yaml: bool = True) -> None:
    """
    Set up centralized logging configuration.

    Args:
        config_path: Path to logging configuration YAML file.
                     Defaults to 'config/logging.yml'
        use_yaml: Whether to attempt YAML loading. Falls back to defaults.
    """
    if config_path is None:
        config_path = Path(__file__).parent.parent.parent / "config" / "logging.yml"

    config = None

    if use_yaml and str(config_path).endswith('.yml'):
        config = _load_yaml_config(str(config_path))

    if config is None:
        config = _get_default_config()

    # Apply environment variable overrides
    config = _apply_env_overrides(config)

    # Configure logging
    logging.config.dictConfig(config)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the specified name.

    This is a convenience function that ensures logging is set up
    before returning the logger.

    Args:
        name: Logger name, typically __name__

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


def set_log_level(level: str) -> None:
    """
    Convenience function to set the root logger level.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    logging.getLogger().setLevel(getattr(logging, level.upper()))