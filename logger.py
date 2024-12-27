import logging, os, sys

LOG_FILE = "./bot.log"

class _ColorFormatter(logging.Formatter):
    LEVEL_COLORS = [
        (logging.DEBUG, "\x1b[34;1m"),
        (logging.INFO, "\x1b[32;1m"),
        (logging.WARNING, "\x1b[33;1m"),
        (logging.ERROR, "\x1b[31m"),
        (logging.CRITICAL, "\x1b[41m"),
    ]

    FORMATS = {
        level: logging.Formatter(
            f"\x1b[30;1m%(asctime)s\x1b[0m {color}%(levelname)-8s\x1b[0m \x1b[35m%(module)s:%(lineno)s\x1b[0m %(message)s",
            "%Y-%m-%d %H:%M:%S",
        )
        for level, color in LEVEL_COLORS
    }

    def format(self, record):
        # Get the appropriate formatter based on the logging level
        formatter = self.FORMATS.get(record.levelno)
        if formatter is None:
            formatter = self.FORMATS[logging.DEBUG]

        # Override the traceback to always print in red
        if record.exc_info:
            text = formatter.formatException(record.exc_info)
            record.exc_text = f"\x1b[31m{text}\x1b[0m"

        output = formatter.format(record)

        # Remove the cache layer
        record.exc_text = None
        return output


def isDocker() -> bool:
    """ Check if the code is running inside a Docker container """
    path = "/proc/self/cgroup"
    return os.path.exists("/.dockerenv") or (os.path.isfile(path) and any("docker" in line for line in open(path)))

def streamSupportsColor(stream) -> bool:
    """ Check if the stream supports color output """
    isTTY = hasattr(stream, "isatty") and stream.isatty()

    # Pycharm and Vscode support color in their inbuilt editors
    if "PYCHARM_HOSTED" in os.environ or os.environ.get("TERM_PROGRAM") == "vscode":
        return isTTY

    if sys.platform != "win32":
        # Docker does not consistently have a tty attached to it
        return isTTY or isDocker()

    # ANSICON checks for things like ConEmu
    # WT_SESSION checks if this is Windows Terminal
    return isTTY and ("ANSICON" in os.environ or "WT_SESSION" in os.environ)


# Configure the logger
logger = logging.getLogger() # root
level = logging.DEBUG
handler = logging.StreamHandler()
dtFormat = "%Y-%m-%d %H:%M:%S"
formatter = logging.Formatter("[{asctime}] [{levelname:<8}] [{module}:{lineno}]: {message}", dtFormat, style="{")

# Set the appropriate formatter based on stream support for color
if isinstance(handler, logging.StreamHandler) and streamSupportsColor(handler.stream):
    handler.setFormatter(_ColorFormatter())
else:
    handler.setFormatter(formatter)

logger.setLevel(level)
logger.addHandler(handler)

# Add file handler to write logs to a file and clear logs on new sessions
fileHandler = logging.FileHandler(LOG_FILE, mode="w")
fileHandler.setFormatter(formatter)
logger.addHandler(fileHandler)
