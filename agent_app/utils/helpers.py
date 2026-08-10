"""
Helper functions for the Industrial Time Series Agent System.
"""

import asyncio
import os
import time
import functools
from typing import Dict, Any, Callable, Optional
from logging import Logger
import logging


def format_response(
    success: bool,
    message: str,
    data: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None
) -> Dict[str, Any]:
    """
    Format a standardized response structure.

    Args:
        success: Whether the operation was successful
        message: Response message
        data: Optional data dictionary
        error: Optional error message

    Returns:
        Formatted response dictionary
    """
    response = {
        'success': success,
        'message': message,
        'timestamp': time.time()
    }

    if data is not None:
        response['data'] = data

    if error is not None:
        response['error'] = error

    return response


def validate_file_path(file_path: str) -> tuple[bool, Optional[str]]:
    """
    Validate if a file path exists and is accessible.

    Args:
        file_path: Path to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not file_path:
        return False, "文件路径不能为空"

    if not os.path.exists(file_path):
        return False, f"文件不存在: {file_path}"

    if not os.path.isfile(file_path):
        return False, f"路径不是文件: {file_path}"

    # Check file extension
    valid_extensions = ['.csv', '.xlsx', '.parquet']
    file_ext = os.path.splitext(file_path)[1].lower()
    if file_ext not in valid_extensions:
        return False, f"不支持的文件格式: {file_ext}. 支持的格式: {', '.join(valid_extensions)}"

    # Check file size (max 100MB)
    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    if file_size_mb > 100:
        return False, f"文件过大 ({file_size_mb:.1f}MB). 最大支持 100MB"

    return True, None


def create_response_structure(
    response_type: str,
    content: Any,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a structured response for different types of outputs.

    Args:
        response_type: Type of response ('text', 'json', 'report')
        content: Main content
        metadata: Optional metadata

    Returns:
        Structured response dictionary
    """
    response = {
        'type': response_type,
        'content': content
    }

    if metadata:
        response['metadata'] = metadata

    return response


def handle_errors(
    default_return: Any = None,
    reraise: bool = False
) -> Callable:
    """
    Decorator for handling errors in functions.

    Args:
        default_return: Default return value on error
        reraise: Whether to reraise the exception

    Returns:
        Decorated function
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logging.error(f"Error in {func.__name__}: {str(e)}", exc_info=True)

                if reraise:
                    raise

                if default_return is not None:
                    if isinstance(default_return, dict) and 'error' not in default_return:
                        default_return['error'] = str(e)
                        default_return['success'] = False
                    return default_return

                return {
                    'success': False,
                    'error': str(e),
                    'message': f"操作失败: {func.__name__}"
                }

        return wrapper
    return decorator


def log_execution_time(func: Callable) -> Callable:
    """
    Decorator for logging function execution time.

    Sync-and-async aware: if ``func`` is a coroutine function we wrap it
    in an ``async def`` so the timer measures the actual awaited
    execution rather than the (instant) coroutine-creation time.

    Args:
        func: Function to decorate

    Returns:
        Decorated function
    """
    if asyncio.iscoroutinefunction(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                return await func(*args, **kwargs)
            finally:
                execution_time = time.time() - start_time
                logging.info(f"{func.__name__} executed in {execution_time:.2f} seconds")
        return async_wrapper

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        execution_time = time.time() - start_time

        logging.info(f"{func.__name__} executed in {execution_time:.2f} seconds")
        return result

    return wrapper


def sanitize_input(input_string: str, max_length: int = 1000) -> str:
    """
    Sanitize user input to prevent injection attacks.

    Args:
        input_string: Input string to sanitize
        max_length: Maximum allowed length

    Returns:
        Sanitized string
    """
    if not isinstance(input_string, str):
        return ""

    # Truncate if too long
    if len(input_string) > max_length:
        input_string = input_string[:max_length]

    # Remove potentially dangerous characters
    dangerous_chars = ['<', '>', '\x00', '\n', '\r']
    for char in dangerous_chars:
        input_string = input_string.replace(char, '')

    return input_string.strip()


def validate_session_id(session_id: str) -> tuple[bool, Optional[str]]:
    """
    Validate session ID format.

    Args:
        session_id: Session ID to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not session_id:
        return False, "Session ID 不能为空"

    if not isinstance(session_id, str):
        return False, "Session ID 必须是字符串"

    if len(session_id) < 10 or len(session_id) > 100:
        return False, "Session ID 长度无效"

    return True, None


def extract_file_info(file_path: str) -> Dict[str, Any]:
    """
    Extract information about a file.

    Args:
        file_path: Path to file

    Returns:
        Dictionary with file information
    """
    if not os.path.exists(file_path):
        return {'error': 'File not found'}

    return {
        'name': os.path.basename(file_path),
        'size_bytes': os.path.getsize(file_path),
        'size_mb': os.path.getsize(file_path) / (1024 * 1024),
        'extension': os.path.splitext(file_path)[1].lower(),
        'absolute_path': os.path.abspath(file_path),
        'exists': True
    }


def merge_dicts(dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge two dictionaries recursively.

    Args:
        dict1: First dictionary
        dict2: Second dictionary

    Returns:
        Merged dictionary
    """
    result = dict1.copy()

    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_dicts(result[key], value)
        else:
            result[key] = value

    return result


def truncate_text(text: str, max_length: int = 200, suffix: str = "...") -> str:
    """
    Truncate text to maximum length.

    Args:
        text: Text to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text

    return text[:max_length - len(suffix)] + suffix


def calculate_percentile(values: list, percentile: float) -> float:
    """
    Calculate percentile of values.

    Args:
        values: List of values
        percentile: Percentile to calculate (0-100)

    Returns:
        Percentile value
    """
    if not values:
        return 0.0

    sorted_values = sorted(values)
    k = (len(sorted_values) - 1) * (percentile / 100)
    f = int(k)
    c = k - f

    if f + 1 < len(sorted_values):
        return sorted_values[f] + c * (sorted_values[f + 1] - sorted_values[f])
    else:
        return sorted_values[f]


def format_large_number(number: float) -> str:
    """
    Format large numbers with appropriate units.

    Args:
        number: Number to format

    Returns:
        Formatted string
    """
    if abs(number) >= 1e9:
        return f"{number / 1e9:.1f}B"
    elif abs(number) >= 1e6:
        return f"{number / 1e6:.1f}M"
    elif abs(number) >= 1e3:
        return f"{number / 1e3:.1f}K"
    else:
        return f"{number:.1f}"


def create_progress_tracker(total_steps: int) -> Dict[str, Any]:
    """
    Create a progress tracker for multi-step operations.

    Args:
        total_steps: Total number of steps

    Returns:
        Progress tracker dictionary
    """
    return {
        'total_steps': total_steps,
        'completed_steps': 0,
        'current_step': 0,
        'percentage': 0.0,
        'steps_completed': [],
        'start_time': time.time(),
        'last_update': time.time()
    }


def update_progress(progress_tracker: Dict[str, Any], step: int) -> Dict[str, Any]:
    """
    Update progress tracker.

    Args:
        progress_tracker: Progress tracker dictionary
        step: Step number that was completed

    Returns:
        Updated progress tracker
    """
    progress_tracker['completed_steps'] += 1
    progress_tracker['current_step'] = step
    progress_tracker['percentage'] = (progress_tracker['completed_steps'] / progress_tracker['total_steps']) * 100
    progress_tracker['steps_completed'].append(step)
    progress_tracker['last_update'] = time.time()

    return progress_tracker


def get_time_ago(timestamp: float) -> str:
    """
    Get human-readable time ago string.

    Args:
        timestamp: Unix timestamp

    Returns:
        Time ago string
    """
    seconds = time.time() - timestamp

    if seconds < 60:
        return f"{int(seconds)}秒前"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes}分钟前"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f"{hours}小时前"
    else:
        days = int(seconds / 86400)
        return f"{days}天前"


class RateLimiter:
    """Simple rate limiter for API calls."""

    def __init__(self, max_calls: int = 100, time_window: int = 60):
        """
        Initialize rate limiter.

        Args:
            max_calls: Maximum number of calls allowed
            time_window: Time window in seconds
        """
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls = []

    def is_allowed(self) -> bool:
        """
        Check if call is allowed.

        Returns:
            True if call is allowed, False otherwise
        """
        current_time = time.time()

        # Remove old calls outside time window
        self.calls = [call_time for call_time in self.calls if current_time - call_time < self.time_window]

        # Check if limit reached
        if len(self.calls) >= self.max_calls:
            return False

        # Add current call
        self.calls.append(current_time)
        return True

    def get_reset_time(self) -> float:
        """
        Get time when rate limit will reset.

        Returns:
            Unix timestamp of reset time
        """
        if not self.calls:
            return time.time()

        return self.calls[0] + self.time_window


def deep_copy_dict(original: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a deep copy of a dictionary.

    Args:
        original: Original dictionary

    Returns:
        Deep copy of dictionary
    """
    import copy
    return copy.deepcopy(original)
