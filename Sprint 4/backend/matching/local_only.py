"""
Guard for the dev scripts (migrate.py, demo_data.py): they must only ever
touch a database on this machine, never the shared Supabase one.

It checks DATABASE_URL from the environment BEFORE anything imports
database.py (which would connect), the same way tests/conftest.py does.
"""

import os
import sys
from urllib.parse import urlparse

LOCAL_HOSTS = ("localhost", "127.0.0.1")


def require_local_database_url() -> str:
    url = os.environ.get("DATABASE_URL", "")
    host = urlparse(url).hostname
    if host not in LOCAL_HOSTS:
        sys.exit(
            "Refusing to run: DATABASE_URL must point to a local Postgres "
            f"(localhost or 127.0.0.1), got host {host!r}.\n"
            "Set it in the same command, for example (PowerShell):\n"
            "  $env:DATABASE_URL='postgresql+pg8000://postgres:postgres@localhost:5432/careerconnect_local'; "
            "python -m matching.demo_data"
        )
    return url
