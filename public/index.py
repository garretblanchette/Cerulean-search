import os
import sys

# Ensure project root is on sys.path when running as a Vercel serverless function
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.main import app  # noqa: E402
