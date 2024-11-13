import datetime
import os

DEBUG = "DEBUG_ADMIN_MIGRATIONS" in os.environ

if DEBUG:
    MAX_MIGRATE = 1
    MAX_SECONDS = 50 * 60
    MAX_WORKERS = 1
else:
    MAX_MIGRATE = 100
    MAX_SECONDS = min(50, max(60 - datetime.datetime.now().minute - 6, 0)) * 60
    MAX_WORKERS = 2
