import sys, traceback, pytz

from datetime import datetime
from colorama import Fore, Style  # type: ignore

LOG_FILE = "./bot.log"
STD_OUT = sys.stdout

class Logger:
    def __init__(self) -> None:
        with open(LOG_FILE, "w") as f:
            f.write("")

    def stop(self) -> None:
        STD_OUT.flush()

    def _log(self, level: str, message: str, flush=False) -> None:
        """ Log message.

        Parameters:
        level (str): (DEBUG | INFO | WARNING | ERROR | CRITICAL).
        message (str): Message to log.
        skipFileSwitchCheck (bool, optional): Whether or not to skip check for switching log file. Defaults to False.
        flush (bool, optional): Whether or not to flush buffers after writing the message. Defaults to False.
        """
        now = datetime.now().astimezone(pytz.timezone("Europe/Paris")).strftime("%Y-%m-%d %H:%M:%S")
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
        with open(LOG_FILE, "a") as f:
            f.write(f">>> {now} : {level} : {message}\n")

    def debug(self, message: str, flush=False) -> None:
        """ Log debug message """
        self._log("DEBUG", message, flush)

    def info(self, message: str, flush=False) -> None:
        """ Log info message """
        self._log("INFO", message, flush)

    def warning(self, message: str, flush=False) -> None:
        """ Log warning message """
        self._log("WARNING", message, flush)

    def error(self, message: str, flush=False) -> None:
        """ Log error message """
        self._log("ERROR", message, flush)

    def critical(self, message: str, flush=False) -> None:
        """ Log critical message """
        self._log("CRITICAL", message, flush)

    def exception(self, message: str, flush=False) -> None:
        """ Log error message followed by traceback """
        self._log("ERROR", f"{message}\n{traceback.format_exc()}", flush)
