"""Shared extension instances that both app.py and route blueprints need to
import, kept in their own module to avoid app.py <-> routes.* circular imports."""
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# storage_uri='memory://' is single-process only. A multi-worker production
# deploy (gunicorn with >1 worker, etc.) needs a shared backend (e.g. Redis)
# or each worker enforces its own separate limits -- flagged here rather than
# silently under-protecting if this app is ever scaled out that way.
limiter = Limiter(key_func=get_remote_address, storage_uri='memory://')
