from logging import basicConfig, getLogger, INFO, WARNING
from dotenv import load_dotenv
from os import getenv

basicConfig(format='[%(levelname)s]: %(name)s.py|%(funcName)s(%(lineno)d): %(message)s', level=INFO)
load_dotenv()

httpx_logger = getLogger('httpx')
httpx_logger.setLevel(WARNING)

TOKEN = getenv('USER_AUTH', '')
PREFIX = '.'
CACHE_CHANNEL = 0
GIF_NAME = '.gif'
DEFAULT_LINE = 'made w/ <3'
DEFAULT_COVER = 'L4NDBxhCjUO4q4dO_VlTd9zd9UctQ38AkVh7-f0jrfM/https/files.catbox.moe/uuxijp.png'
