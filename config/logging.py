import logging
import sys

# Check if colorama is installed, if not, install it
try:
    from colorama import init, Fore
except ImportError:
    print("Installing colorama for colored console output...")
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "colorama"])
    from colorama import init, Fore

# Initialize colorama
init(autoreset=True)

class Logger:
    """Logger class that logs messages to the console with color formatting."""

    COLOR_MAP = {
        logging.DEBUG: Fore.BLUE,      # Blue for Debug
        logging.INFO: Fore.GREEN,      # Green for Info
        logging.WARNING: Fore.YELLOW,  # Yellow for Warning
        logging.ERROR: Fore.RED,       # Red for Error
        logging.CRITICAL: Fore.MAGENTA # Magenta for Critical
    }

    class ColoredFormatter(logging.Formatter):
        """Custom formatter to apply colors to log levels."""
        def format(self, record):
            log_color = Logger.COLOR_MAP.get(record.levelno, Fore.WHITE)
            log_message = super().format(record)
            return f"{log_color}{log_message}{Fore.RESET}"

    def __init__(self, name=__name__, level=logging.INFO):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)

        # Custom formatter
        formatter = self.ColoredFormatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(formatter)

        # Avoid adding multiple handlers
        if not self.logger.hasHandlers():
            self.logger.addHandler(console_handler)

    def get_logger(self):
        return self.logger

# Usage example
logger = Logger().get_logger()