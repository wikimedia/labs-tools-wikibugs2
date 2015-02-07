import os
import sys
import logging
import logging.handlers
import argparse


def private_open(file, flags, dir_fd=None):
    return os.open(file, flags, mode=0o600, dir_fd=dir_fd)


class PrivateTimedRotatingFileHandler(logging.handlers.TimedRotatingFileHandler):
    def _open(self):
        return open(self.baseFilename, self.mode, encoding=self.encoding, opener=private_open)


class LoggingSetupParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        super(LoggingSetupParser, self).__init__(*args, **kwargs)
        self.add_argument(
            "--logfile", dest='logfile', default=None,
            help="Log to this (rotated) log file; if not provided, log to stdout",
        )

    def parse_args(self, *args, **kwargs):
        result = super(LoggingSetupParser, self).parse_args(*args, **kwargs)
        self.set_up_logging(result)
        return result

    def set_up_logging(self, args):
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)

        if args.logfile:
            handler = PrivateTimedRotatingFileHandler(
                args.logfile,
                when='midnight', backupCount=7,
                utc=True
            )
            print("Logging to %s" % args.logfile)
        else:
            handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
