import datetime
import os

DEBUG = "DEBUG_ADMIN_MIGRATIONS" in os.environ


def _compute_max_migrate_minutes():
    now = datetime.datetime.now(datetime.UTC)
    max_mins = 60 - now.minute - 6

    if max_mins < 0:
        max_mins = 0

    if max_mins > 50:
        max_mins = 50

    return max_mins


if DEBUG:
    MAX_MIGRATE = 1
    MAX_SECONDS = 50 * 60
    MAX_WORKERS = 1
else:
    MAX_MIGRATE = 2000
    MAX_SECONDS = _compute_max_migrate_minutes() * 60
    MAX_WORKERS = 2
