"""Module for reading configuration data from INI files."""
import os
import logging
import configparser
from typing import List

# Constants
ERROR_VALUE = 'error'

# Configure module-level logger
logger = logging.getLogger(__name__)


class INIReadError(Exception):
    """Custom exception for INI file reading errors."""
    pass


def get_data_ini(file_path: str, tag_name: str, file_check: bool = False) -> List[str]:
    """
    Parse an INI file and return a list of values for the given tag/section.
    
    This is the modern function name following Python naming conventions.
    For backward compatibility, use getDataINI() instead.
    
    Args:
        file_path: Path to the INI file
        tag_name: The key name to retrieve from the configuration
        file_check: If True, verify that the results are real files
    
    Returns:
        List of string values for the given tag, or [ERROR_VALUE] if file doesn't exist
        or if an error occurs. Exceptions are caught and logged for backward compatibility.
    """
    return _get_data_ini_impl(file_path, tag_name, file_check)


def getDataINI(file_path: str, tag_name: str, file_check: int = 0) -> List[str]:
    """
    Legacy function name for backward compatibility.
    
    Args:
        file_path: Path to the INI file
        tag_name: The key name to retrieve from the configuration
        file_check: If 1, verify that the results are real files
    
    Returns:
        List of string values for the given tag, or [ERROR_VALUE] if file doesn't exist
        or if an error occurs. Exceptions are caught and logged for backward compatibility.
    """
    return _get_data_ini_impl(file_path, tag_name, bool(file_check))


def _get_data_ini_impl(file_path: str, tag_name: str, file_check: bool = False) -> List[str]:
    """
    Parse an INI file and return a list of values for the given tag/section.
    
    This function searches for the tag_name in all sections of the INI file.
    If the same key exists in multiple sections, all values will be returned.
    
    For backward compatibility, all exceptions are caught and [ERROR_VALUE] is returned
    instead of raising exceptions. Errors are logged for debugging purposes.
    
    Args:
        file_path: Path to the INI file
        tag_name: The key name to retrieve from the configuration
        file_check: If True, verify that the results are real files
    
    Returns:
        List of string values for the given tag, or [ERROR_VALUE] if:
        - File doesn't exist
        - Tag not found in any section
        - file_check is True and any returned path doesn't exist
        - Any parsing or I/O error occurs
    """
    if not file_path:
        logger.warning("Empty file_path provided to getDataINI")
        return [ERROR_VALUE]
    
    if not os.path.exists(file_path):
        logger.warning(f"INI file not found: {file_path}")
        return [ERROR_VALUE]
    
    try:
        config = configparser.ConfigParser()
        # Use read() with encoding for better compatibility
        # Note: read() returns list of successfully read files
        read_files = config.read(file_path, encoding='utf-8')
        if not read_files:
            logger.error(f"Failed to read INI file (may be empty or invalid): {file_path}")
            return [ERROR_VALUE]
    except configparser.Error as e:
        # Handle parsing errors (MissingSectionHeaderError, etc.)
        logger.error(f"Failed to parse INI file '{file_path}': {e}", exc_info=True)
        return [ERROR_VALUE]
    except Exception as e:
        # Handle other unexpected errors (permission issues, etc.)
        logger.error(f"Unexpected error reading INI file '{file_path}': {e}", exc_info=True)
        return [ERROR_VALUE]
    
    data_list = []
    
    # Try to find the value in all sections
    for section_name in config.sections():
        if config.has_option(section_name, tag_name):
            try:
                value = config.get(section_name, tag_name)
                # Handle values that might contain spaces - preserve them
                data_list.append(value)
            except (configparser.NoOptionError, configparser.NoSectionError):
                # Should not happen due to has_option check, but handle gracefully
                logger.debug(f"Unexpected error getting option '{tag_name}' from section '{section_name}'")
                continue
            except Exception as e:
                logger.warning(f"Error reading option '{tag_name}' from section '{section_name}': {e}")
                continue
    
    # If not found in sections, try DEFAULT section
    if not data_list and config.has_option(configparser.DEFAULTSECT, tag_name):
        try:
            value = config.get(configparser.DEFAULTSECT, tag_name)
            data_list.append(value)
        except (configparser.NoOptionError, configparser.NoSectionError):
            pass
        except Exception as e:
            logger.warning(f"Error reading option '{tag_name}' from DEFAULT section: {e}")
    
    # If file_check is enabled, verify all returned paths exist
    if file_check:
        for item in data_list:
            if not os.path.exists(item):
                logger.warning(f"File check failed: path does not exist: {item}")
                return [ERROR_VALUE]
    
    if not data_list:
        logger.debug(f"Tag '{tag_name}' not found in INI file: {file_path}")
        return [ERROR_VALUE]
    
    return data_list
