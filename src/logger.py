"""
This module provides a Logger class that outputs to both console and file simultaneously.
"""

import os
import sys
from datetime import datetime
from enum import Enum
from typing import Optional, TextIO


class LogLevel(Enum):
    """Log severity levels"""
    DEBUG = 0
    INFO = 1
    WARNING = 2
    ERROR = 3
    CRITICAL = 4


class Logger:
    """
    Logger class for simulation output.

    Supports simultaneous output to console and file,
    with configurable log levels and formatting.
    """

    # ANSI color codes for console output
    COLORS = {
        LogLevel.DEBUG: '\033[36m',     # Cyan
        LogLevel.INFO: '\033[32m',      # Green
        LogLevel.WARNING: '\033[33m',   # Yellow
        LogLevel.ERROR: '\033[31m',     # Red
        LogLevel.CRITICAL: '\033[35m',  # Magenta
    }
    RESET = '\033[0m'

    def __init__(
        self,
        name: str = "BoxCarSimulation",
        log_file: Optional[str] = None,
        console_level: LogLevel = LogLevel.INFO,
        file_level: LogLevel = LogLevel.DEBUG,
        use_colors: bool = True,
        timestamp_format: str = "%Y-%m-%d %H:%M:%S"
    ):
        """
        Initialize the logger.

        Args:
            name: Logger name (appears in log messages)
            log_file: Path to log file (None = auto-generate)
            console_level: Minimum level for console output
            file_level: Minimum level for file output
            use_colors: Whether to use ANSI colors in console
            timestamp_format: Format string for timestamps
        """
        self.name = name
        self.console_level = console_level
        self.file_level = file_level
        self.use_colors = use_colors
        self.timestamp_format = timestamp_format

        self._file_handle: Optional[TextIO] = None
        self._log_file_path: Optional[str] = None

        # Auto-generate log file path if not specified
        if log_file is None:
            self._setup_auto_log_file()
        else:
            self._setup_log_file(log_file)

    def _setup_auto_log_file(self):
        """Create auto-generated log file in output directory"""
        # Create output directory if it doesn't exist
        output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'output')
        os.makedirs(output_dir, exist_ok=True)

        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"simulation_{timestamp}.log"
        log_path = os.path.join(output_dir, log_filename)

        self._setup_log_file(log_path)

    def _setup_log_file(self, log_path: str):
        """Set up log file for writing"""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(log_path) if os.path.dirname(log_path) else '.', exist_ok=True)
            self._file_handle = open(log_path, 'w', encoding='utf-8')
            self._log_file_path = log_path
            self._write_header()
        except Exception as e:
            print(f"Warning: Could not open log file {log_path}: {e}")
            self._file_handle = None

    def _write_header(self):
        """Write header to log file"""
        if self._file_handle:
            header = [
                "=" * 70,
                f"BoxCar Ride-Sharing Simulation Log",
                f"Started: {datetime.now().strftime(self.timestamp_format)}",
                f"Logger: {self.name}",
                "=" * 70,
                ""
            ]
            self._file_handle.write('\n'.join(header) + '\n')
            self._file_handle.flush()

    def _format_message(self, level: LogLevel, message: str,
                        simulation_time: Optional[float] = None,
                        for_console: bool = True) -> str:
        """Format a log message"""
        timestamp = datetime.now().strftime(self.timestamp_format)
        level_str = f"[{level.name:8}]"

        # Add simulation time if provided
        sim_time_str = ""
        if simulation_time is not None:
            sim_time_str = f" [t={simulation_time:8.4f}h]"

        # Build message
        if for_console and self.use_colors:
            color = self.COLORS.get(level, '')
            return f"{color}{timestamp} {level_str}{sim_time_str} {message}{self.RESET}"
        else:
            return f"{timestamp} {level_str}{sim_time_str} {message}"

    def _log(self, level: LogLevel, message: str,
             simulation_time: Optional[float] = None):
        """Internal logging method"""
        # Console output
        if level.value >= self.console_level.value:
            console_msg = self._format_message(level, message, simulation_time, for_console=True)
            print(console_msg)

        # File output
        if self._file_handle and level.value >= self.file_level.value:
            file_msg = self._format_message(level, message, simulation_time, for_console=False)
            self._file_handle.write(file_msg + '\n')
            self._file_handle.flush()

    def debug(self, message: str, simulation_time: Optional[float] = None):
        """Log debug message"""
        self._log(LogLevel.DEBUG, message, simulation_time)

    def info(self, message: str, simulation_time: Optional[float] = None):
        """Log info message"""
        self._log(LogLevel.INFO, message, simulation_time)

    def warning(self, message: str, simulation_time: Optional[float] = None):
        """Log warning message"""
        self._log(LogLevel.WARNING, message, simulation_time)

    def error(self, message: str, simulation_time: Optional[float] = None):
        """Log error message"""
        self._log(LogLevel.ERROR, message, simulation_time)

    def critical(self, message: str, simulation_time: Optional[float] = None):
        """Log critical message"""
        self._log(LogLevel.CRITICAL, message, simulation_time)

    def event(self, event_type: str, entity_id: int, details: str,
              simulation_time: float):
        """Log a simulation event"""
        message = f"EVENT: {event_type:25} | Entity: {entity_id:6} | {details}"
        self._log(LogLevel.DEBUG, message, simulation_time)

    def stats(self, category: str, metrics: dict):
        """Log statistics"""
        self.info(f"--- {category} Statistics ---")
        for key, value in metrics.items():
            if isinstance(value, float):
                self.info(f"  {key}: {value:.4f}")
            else:
                self.info(f"  {key}: {value}")

    def section(self, title: str):
        """Log a section header"""
        separator = "=" * 60
        self._log(LogLevel.INFO, separator)
        self._log(LogLevel.INFO, f"  {title}")
        self._log(LogLevel.INFO, separator)

    def subsection(self, title: str):
        """Log a subsection header"""
        self._log(LogLevel.INFO, f"--- {title} ---")

    def progress(self, current: int, total: int, prefix: str = "Progress"):
        """Log progress update"""
        percentage = current / total * 100 if total > 0 else 0
        bar_length = 30
        filled = int(bar_length * current / total) if total > 0 else 0
        bar = '█' * filled + '░' * (bar_length - filled)
        message = f"{prefix}: [{bar}] {current}/{total} ({percentage:.1f}%)"
        self._log(LogLevel.INFO, message)

    def table(self, headers: list, rows: list, title: str = None):
        """Log a formatted table"""
        if title:
            self.info(title)

        # Calculate column widths
        widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                widths[i] = max(widths[i], len(str(cell)))

        # Format header
        header_row = " | ".join(f"{h:{widths[i]}}" for i, h in enumerate(headers))
        separator = "-+-".join("-" * w for w in widths)

        self.info(header_row)
        self.info(separator)

        # Format rows
        for row in rows:
            row_str = " | ".join(f"{str(cell):{widths[i]}}" for i, cell in enumerate(row))
            self.info(row_str)

    def get_log_file_path(self) -> Optional[str]:
        """Get the path to the log file"""
        return self._log_file_path

    def close(self):
        """Close the log file"""
        if self._file_handle:
            self._write_footer()
            self._file_handle.close()
            self._file_handle = None

    def _write_footer(self):
        """Write footer to log file"""
        if self._file_handle:
            footer = [
                "",
                "=" * 70,
                f"Log ended: {datetime.now().strftime(self.timestamp_format)}",
                "=" * 70
            ]
            self._file_handle.write('\n'.join(footer) + '\n')

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
        return False


# Global logger instance
_default_logger: Optional[Logger] = None


def get_logger(name: str = "BoxCarSimulation", **kwargs) -> Logger:
    """
    Get or create a logger instance.

    Args:
        name: Logger name
        **kwargs: Additional arguments for Logger constructor

    Returns:
        Logger instance
    """
    global _default_logger
    if _default_logger is None:
        _default_logger = Logger(name=name, **kwargs)
    return _default_logger


def set_logger(logger: Logger):
    """Set the global logger instance"""
    global _default_logger
    _default_logger = logger


def reset_logger():
    """Reset the global logger"""
    global _default_logger
    if _default_logger:
        _default_logger.close()
    _default_logger = None
