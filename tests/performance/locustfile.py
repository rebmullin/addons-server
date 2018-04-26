import logging
import os
import sys
import time

# due to locust sys.path manipulation, we need to re-add the project root.
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# Now we can load django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')

import olympia.lib.safe_xml

from locust import HttpLocust  # noqa
from locust.log import setup_logging

from behaviors.user import (
    AnonymousUserBehavior,
    RegisteredUserBehavior
)  # noqa
import helpers  # noqa

logging.Formatter.converter = time.gmtime

setup_logging('DEBUG', None)

helpers.install_event_markers()


class AnonymousUser(HttpLocust):
    task_set = AnonymousUserBehavior
    min_wait = 5000
    max_wait = 9000

    def __init__(self):
        super(AnonymousUser, self).__init__()


class RegisteredUserBehavior(HttpLocust):
    task_set = RegisteredUserBehavior
    min_wait = 5000
    max_wait = 9000
