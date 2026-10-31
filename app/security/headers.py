"""Security response headers, applied to every response via app.after_request.

This app is same-origin by design: one Flask process serves both the
server-rendered Jinja pages and the built React SPA (see app.py's
_serve_spa()). There is no legitimate external caller today, so CORS is
deliberately left closed -- no flask-cors, no Access-Control-Allow-Origin
header anywhere. If a future integration (mobile app, third party) needs
cross-origin API access, that should be a scoped addition of specific
allowed origins, not a blanket `*`.
"""

CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "img-src 'self' data:; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)
# style-src needs 'unsafe-inline' because Jinja templates use inline
# style="..." attributes throughout -- refactoring all of them to CSS
# classes is out of scope for this pass; this is a deliberate trade-off,
# not an oversight. script-src has no 'unsafe-inline'/'unsafe-eval' since
# the built SPA loads a single hashed module script and nothing inline.


def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Content-Security-Policy'] = CSP

    from flask import request
    if request.is_secure:
        # Only sent over an actual HTTPS connection -- emitting it over plain
        # HTTP (e.g. local dev) would tell the browser to force HTTPS on a
        # host that doesn't serve it.
        response.headers['Strict-Transport-Security'] = 'max-age=63072000; includeSubDomains'

    return response
