# Optional root entrypoint (not required by Vercel when routing to /api/index.py).
# Keeping this prevents "entrypoint not found" issues on other hosts.
from api.index import app  # noqa: F401
