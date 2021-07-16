from datetime import datetime, timedelta, timezone
import traceback
import sys
from colorama import Fore, Style

STD_OUT = sys.stdout

class Logger:
    def stop(self):
        STD_OUT.flush()
    
    def _log(self, level: str, message: str, flush=False):
        """
        Log message.

        Args:
            level (str): (DEBUG | INFO | WARNING | ERROR | CRITICAL)
            message (str): Message to log
            skipFileSwitchCheck (bool, optional): Whether or not to skip check for switching log file. Defaults to False.
            flush (bool, optional): Whether or not to flush buffers after writing the message. Defaults to False.
        """
        now = datetime.now(tz=timezone(timedelta(hours=2))).strftime("%Y-%m-%d %H:%M:%S,%f")
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
    
    def debug(self, message: str, flush=False):
        """
            Log debug message
        """
        self._log("DEBUG", message, flush)
    
    def info(self, message: str, flush=False):
        """
            Log info message
        """
        self._log("INFO", message, flush)
    
    def warning(self, message: str, flush=False):
        """
            Log warning message
        """
        self._log("WARNING", message, flush)
    
    def error(self, message: str, flush=False):
        """
            Log error message
        """
        self._log("ERROR", message, flush)
    
    def critical(self, message: str, flush=False):
        """
            Log critical message
        """
        self._log("CRITICAL", message, flush)
    
    def exception(self, message: str, flush=False):
        """
            Log error message followed by traceback
        """
        self._log("ERROR", f"{message}\n{traceback.format_exc()}", flush)