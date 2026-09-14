#!/usr/bin/env python3
"""
Minimal GitHub OAuth relay for Sveltia / Decap CMS "Sign In with GitHub".

Implements the two endpoints the CMS popup flow needs:
  GET /auth      -> redirect the user to GitHub's authorize page
  GET /callback  -> exchange the returned code for a token and hand it to the
                    CMS popup via window.postMessage

...and a second, separate flow that gates the GoAccess traffic report at
/stats behind the same GitHub identity, so whoever can edit the site can also
read its statistics:
  GET /auth/stats/verify  -> Caddy `forward_auth` probe: 200 if the caller has
                             a valid session cookie, else 302 into the flow
  GET /auth/stats/login   -> start the GitHub flow for /stats
  GET /auth/stats/logout  -> drop the session
  GET /callback           -> shared with the CMS flow above; which one is
                             finishing is decided by the `state` prefix, so the
                             GitHub OAuth App keeps its single callback URL

Authorization for /stats is "can you push to the repo", read straight from
GitHub, so the editor list and the stats-viewer list cannot drift apart.

Standard library only (no third-party dependencies). CSRF-protected with a
short-lived, HttpOnly state cookie. Configuration comes from the environment
(see /etc/nharc-oauth.env):

  GITHUB_CLIENT_ID      OAuth App client id
  GITHUB_CLIENT_SECRET  OAuth App client secret
  OAUTH_SCOPE           GitHub scope to request (default: public_repo)
  REDIRECT_URI          must equal the OAuth App's Authorization callback URL
  ALLOWED_ORIGIN        the CMS origin allowed to receive the token
  PORT                  local listen port (default: 8402)
  SESSION_SECRET        HMAC key for /stats session cookies. Required for the
                        /stats gate; without it the gate denies everyone.
  STATS_REPO            owner/name whose push access grants /stats
  SESSION_TTL           /stats session lifetime in seconds (default: 12h)
"""
import base64
import hashlib
import hmac
import http.cookies
import http.server
import json
import os
import secrets
import socketserver
import time
import urllib.error
import urllib.parse
import urllib.request

CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET", "")
SCOPE = os.environ.get("OAUTH_SCOPE", "public_repo")
REDIRECT_URI = os.environ.get("REDIRECT_URI", "https://newweb.nharc.org/callback")
ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "https://newweb.nharc.org")
PORT = int(os.environ.get("PORT", "8402"))

SESSION_SECRET = os.environ.get("SESSION_SECRET", "")
STATS_REPO = os.environ.get("STATS_REPO", "mark-iid/nharcweb")
SESSION_TTL = int(os.environ.get("SESSION_TTL", "43200"))

GH_AUTHORIZE = "https://github.com/login/oauth/authorize"
GH_TOKEN = "https://github.com/login/oauth/access_token"
GH_API = "https://api.github.com"

# The CMS and the /stats gate share one callback URL (a GitHub OAuth App only
# has one). Which flow is coming back is decided by this prefix on `state`.
STATS_STATE_PREFIX = "stats."
SESSION_COOKIE = "nharc_stats_session"
STATS_STATE_COOKIE = "stats_oauth_state"


def result_page(status, payload_obj):
    """HTML page that posts the auth result back to the CMS window."""
    message = "authorization:github:%s:%s" % (status, json.dumps(payload_obj))
    return (
        "<!doctype html><html><head><meta charset='utf-8'></head><body>"
        "<script>(function(){"
        "var MSG=%s, ORIGIN=%s;"
        "function receive(e){"
        "if(e.origin!==ORIGIN)return;"
        "window.opener.postMessage(MSG,ORIGIN);"
        "window.removeEventListener('message',receive,false);}"
        "window.addEventListener('message',receive,false);"
        "if(window.opener)window.opener.postMessage('authorizing:github',ORIGIN);"
        "})();</script><p>Completing sign-in&hellip; you can close this window.</p>"
        "</body></html>"
    ) % (json.dumps(message), json.dumps(ALLOWED_ORIGIN))


def _b64e(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64d(text):
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(body):
    return _b64e(hmac.new(SESSION_SECRET.encode("utf-8"), body.encode("ascii"),
                          hashlib.sha256).digest())


def sign_session(user):
    """Mint a `<payload>.<hmac>` session value for the /stats gate."""
    payload = json.dumps({"u": user, "exp": int(time.time()) + SESSION_TTL},
                         separators=(",", ":"), sort_keys=True).encode("utf-8")
    body = _b64e(payload)
    return "%s.%s" % (body, _sign(body))


def verify_session(value):
    """Return the username in a valid, unexpired session, else None."""
    # No secret configured means the gate cannot verify anything. Fail closed:
    # better that /stats is unreachable than open to the internet.
    if not value or not SESSION_SECRET:
        return None
    try:
        body, sig = value.split(".", 1)
    except ValueError:
        return None
    if not hmac.compare_digest(sig, _sign(body)):
        return None
    try:
        data = json.loads(_b64d(body))
    except Exception:  # noqa: BLE001 - any malformed cookie is simply invalid
        return None
    if int(data.get("exp", 0)) <= time.time():
        return None
    return data.get("u")


def github_identity(token):
    """(login, can_push) for `token`, or (None, False) if GitHub says no.

    Authorization is deliberately read live from GitHub on each sign-in rather
    than kept in a local list, so removing a collaborator also removes their
    access to /stats with no second place to remember to update.
    """
    def get(url):
        req = urllib.request.Request(url, headers={
            "Authorization": "Bearer %s" % token,
            "Accept": "application/vnd.github+json",
            "User-Agent": "nharc-oauth",
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))

    try:
        login = get("%s/user" % GH_API).get("login")
        # On an authenticated request GitHub reports the caller's own access to
        # the repo in `permissions`, which is exactly the CMS's rule.
        perms = get("%s/repos/%s" % (GH_API, STATS_REPO)).get("permissions") or {}
    except Exception:  # noqa: BLE001 - network/permission failures deny
        return None, False
    return login, bool(perms.get("push"))


def notice_page(heading, detail):
    """Plain page for the /stats flow (the CMS's postMessage page won't do)."""
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>%s</title><style>"
        "body{font:16px/1.5 system-ui,sans-serif;margin:12vh auto;max-width:32rem;"
        "padding:0 1.5rem;color:#222}h1{font-size:1.3rem;color:#006633}"
        "a{color:#006633}</style></head><body><h1>%s</h1><p>%s</p>"
        "<p><a href='/'>Back to nharc.org</a></p></body></html>"
    ) % (heading, heading, detail)


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "nharc-oauth"

    def _html(self, body, status=200, extra_headers=None):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra_headers or {}):
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def _cookie(self, name):
        raw = self.headers.get("Cookie")
        if not raw:
            return None
        try:
            return http.cookies.SimpleCookie(raw)[name].value
        except KeyError:
            return None

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = urllib.parse.parse_qs(parsed.query)

        if path == "/auth":
            return self._start_auth()
        if path == "/callback":
            # One callback URL, two flows — tell them apart by the state prefix.
            state = (query.get("state") or [""])[0]
            if state.startswith(STATS_STATE_PREFIX):
                return self._finish_stats_auth(query)
            return self._finish_auth(query)
        if path == "/auth/stats/verify":
            return self._stats_verify()
        if path == "/auth/stats/login":
            return self._stats_login()
        if path == "/auth/stats/logout":
            return self._stats_logout()
        self.send_error(404)

    def _start_auth(self):
        state = secrets.token_urlsafe(24)
        params = urllib.parse.urlencode({
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "scope": SCOPE,
            "state": state,
            "allow_signup": "false",
        })
        cookie = ("oauth_state=%s; Path=/; Max-Age=600; HttpOnly; Secure; "
                  "SameSite=Lax") % state
        self.send_response(302)
        self.send_header("Location", "%s?%s" % (GH_AUTHORIZE, params))
        self.send_header("Set-Cookie", cookie)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def _finish_auth(self, query):
        code = (query.get("code") or [None])[0]
        state = (query.get("state") or [None])[0]
        expected = self._cookie("oauth_state")
        clear = ("oauth_state=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Lax")

        if not code or not state or state != expected:
            return self._html(
                result_page("error", {"error": "invalid_state",
                                       "provider": "github"}),
                status=400, extra_headers=[("Set-Cookie", clear)])

        try:
            token = self._exchange(code)
        except Exception:  # noqa: BLE001 - relay must not leak internals
            token = None

        if not token:
            return self._html(
                result_page("error", {"error": "token_exchange_failed",
                                       "provider": "github"}),
                status=502, extra_headers=[("Set-Cookie", clear)])

        return self._html(
            result_page("success", {"token": token, "provider": "github"}),
            extra_headers=[("Set-Cookie", clear)])

    # --- /stats gate -----------------------------------------------------

    def _redirect(self, location, extra_headers=None):
        self.send_response(302)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra_headers or []):
            self.send_header(k, v)
        self.end_headers()

    def _stats_verify(self):
        """Caddy `forward_auth` probe. 2xx lets the request through."""
        user = verify_session(self._cookie(SESSION_COOKIE))
        if not user:
            # Caddy hands any non-2xx straight back to the browser, so this
            # redirect is what an unauthenticated visitor actually follows.
            return self._redirect("/auth/stats/login")
        self.send_response(200)
        self.send_header("X-Stats-User", user)
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def _stats_login(self):
        if not SESSION_SECRET:
            return self._html(notice_page(
                "Statistics unavailable",
                "The server is missing SESSION_SECRET, so sign-in is disabled."),
                status=503)
        state = STATS_STATE_PREFIX + secrets.token_urlsafe(24)
        params = urllib.parse.urlencode({
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "scope": SCOPE,
            "state": state,
            "allow_signup": "false",
        })
        cookie = ("%s=%s; Path=/; Max-Age=600; HttpOnly; Secure; "
                  "SameSite=Lax") % (STATS_STATE_COOKIE, state)
        self._redirect("%s?%s" % (GH_AUTHORIZE, params),
                       [("Set-Cookie", cookie)])

    def _stats_logout(self):
        drop = ("%s=; Path=/; Max-Age=0; HttpOnly; Secure; "
                "SameSite=Lax") % SESSION_COOKIE
        self._html(notice_page("Signed out", "You have been signed out of the "
                               "traffic report."),
                   extra_headers=[("Set-Cookie", drop)])

    def _finish_stats_auth(self, query):
        code = (query.get("code") or [None])[0]
        state = (query.get("state") or [None])[0]
        expected = self._cookie(STATS_STATE_COOKIE)
        clear = ("%s=; Path=/; Max-Age=0; HttpOnly; Secure; "
                 "SameSite=Lax") % STATS_STATE_COOKIE

        if not code or not state or not expected or state != expected:
            return self._html(
                notice_page("Sign-in failed",
                            "The sign-in link expired or did not match. "
                            "Please try again."),
                status=400, extra_headers=[("Set-Cookie", clear)])

        try:
            token = self._exchange(code)
        except Exception:  # noqa: BLE001 - relay must not leak internals
            token = None
        if not token:
            return self._html(
                notice_page("Sign-in failed",
                            "GitHub did not return a token. Please try again."),
                status=502, extra_headers=[("Set-Cookie", clear)])

        login, can_push = github_identity(token)
        if not can_push:
            who = (" as <strong>%s</strong>" % login) if login else ""
            return self._html(
                notice_page(
                    "Not authorized",
                    "You signed in%s, but that account cannot push to "
                    "%s. The traffic report is open to the same people who "
                    "can edit the site." % (who, STATS_REPO)),
                status=403, extra_headers=[("Set-Cookie", clear)])

        session = ("%s=%s; Path=/; Max-Age=%d; HttpOnly; Secure; "
                   "SameSite=Lax") % (SESSION_COOKIE, sign_session(login),
                                      SESSION_TTL)
        self._redirect("/stats", [("Set-Cookie", clear),
                                  ("Set-Cookie", session)])

    def _exchange(self, code):
        body = urllib.parse.urlencode({
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "code": code,
            "redirect_uri": REDIRECT_URI,
        }).encode("utf-8")
        req = urllib.request.Request(GH_TOKEN, data=body, headers={
            "Accept": "application/json",
            "User-Agent": "nharc-oauth",
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data.get("access_token")

    def log_message(self, fmt, *args):  # keep logs quiet (no tokens/codes)
        pass


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


if __name__ == "__main__":
    Server(("127.0.0.1", PORT), Handler).serve_forever()
