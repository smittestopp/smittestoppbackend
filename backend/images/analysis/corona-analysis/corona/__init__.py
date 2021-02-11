import logging
import sys

__VERSION__ = "2.4.3"

logger = logging.getLogger(__name__)
shdl = logging.StreamHandler()
shdl.setLevel(logging.INFO)
shdl.setFormatter(
    logging.Formatter(
        fmt=f'{ __VERSION__ } %(asctime)s [%(levelname)-8s] %(message)s [%(threadName)s]',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
)
logger.addHandler(shdl)
logger.setLevel(logging.INFO)
logger.propagate = False

if sys.version_info < (3,7,0):
    logging.error("The analysis pipeline needs at least Python 3.7.0")
    exit(1)
