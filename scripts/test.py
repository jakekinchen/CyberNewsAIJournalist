from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import logging
import http.client
import requests

http.client.HTTPConnection.debuglevel = 1

logging.basicConfig()
logging.getLogger().setLevel(logging.DEBUG)
requests_log = logging.getLogger("requests.packages.urllib3")
requests_log.setLevel(logging.DEBUG)
requests_log.propagate = True
