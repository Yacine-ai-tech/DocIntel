"""
Test-session isolation: never let a real POSTGRES_URL from this environment's
.env leak into the test suite.

api.py creates its BatchProcessor/CameraManager singletons once, at module import
time — and core.db.DB_ENABLED is likewise fixed at core.db's first import. Both
happen the moment any test module does `from api import app` (or imports
services.batch_processor / services.camera directly), which is before any
per-test monkeypatching could take effect. Without this, running `pytest tests/`
in a checkout whose .env has a real POSTGRES_URL (as this project's own
production .env does) would write real rows to that real database on every
local test run. This module-level pop runs before pytest imports any test file
or conftest fixture, closing that gap for the whole session.

Individual tests that specifically want to exercise the Postgres-backed path
set POSTGRES_URL back via monkeypatch + importlib.reload for just that test.

Setting an empty string, not popping the key: core/config.py's load_dotenv()
call only skips a variable that's already *present* in os.environ (its default
override=False checks presence, not truthiness) — popping the key makes it
look unset to a later load_dotenv() call (triggered whenever core.config is
first imported, which may happen after this file runs), so dotenv would just
re-read the real value straight back out of .env. An empty string blocks that.
"""
import os

os.environ["POSTGRES_URL"] = ""
