import logging
import pprint
from . import get_group_all

logging.basicConfig(level=logging.DEBUG)
pprint.pprint(get_group_all('console_scripts'))
