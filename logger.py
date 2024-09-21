import os, sys, traceback

from datetime import datetime, timezone
from colorama import Fore, Style  # type: ignore

LOG_FILE = "./bot.log"
STD_OUT = sys.stdout

class Logger:
    def __init__(self) -> None:
        if not os.path.exists("./logs"):
            os.mkdir("logs")
        if os.path.exists(LOG_FILE):
            logFilename = f"./logs/bot.{datetime.now(timezone.utc).strftime('%Y-%m-%d_%H-%M-%S')}.log"
            os.rename(LOG_FILE, logFilename)
        with open(LOG_FILE, "w") as f:
            f.write("")

    @staticmethod
    def _log(level: str, message: str, flush=False) -> None:
        """Log message.

        Parameters:
        level (str): (DEBUG | INFO | WARNING | ERROR | CRITICAL).
        message (str): Message to log.
        flush (bool, optional): Whether or not to flush buffers after writing the message. Defaults to False.
        """
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        levelColors = {
            "DEBUG": Fore.CYAN,
            "INFO": Fore.GREEN,
            "WARNING": Fore.YELLOW,
            "ERROR": Fore.RED,
            "CRITICAL": Fore.MAGENTA
        }
        logStrPrint = f"{levelColors[level]}>>> {now} : {level} : {message}\n{Style.RESET_ALL}"
        STD_OUT.write(logStrPrint)
        if flush:
            STD_OUT.flush()
        try:
            with open(LOG_FILE, "a") as f:
                f.write(f">>> {now} : {level} : {message}\n")
        except Exception:
            pass

    @staticmethod
    def debug(message: str, flush=False) -> None:
        """ Log debug message """
        Logger._log("DEBUG", message, flush)

    @staticmethod
    def info(message: str, flush=False) -> None:
        """ Log info message """
        Logger._log("INFO", message, flush)

    @staticmethod
    def warning(message: str, flush=False) -> None:
        """ Log warning message """
        Logger._log("WARNING", message, flush)

    @staticmethod
    def error(message: str, flush=False) -> None:
        """ Log error message """
        Logger._log("ERROR", message, flush)

    @staticmethod
    def critical(message: str, flush=False) -> None:
        """ Log critical message """
        Logger._log("CRITICAL", message, flush)

    @staticmethod
    def exception(message: str | Exception, flush=False) -> None:
        """ Log error message followed by traceback """
        Logger._log("ERROR", f"{message}\n{traceback.format_exc()}", flush)
