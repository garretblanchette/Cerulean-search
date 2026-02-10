# Optional root entrypoint for platforms that look for index.py at repo root.
# Vercel should use /api/index.py, but keeping this prevents "entrypoint not found" on other hosts.
from api.index import app  # noqa: F401
