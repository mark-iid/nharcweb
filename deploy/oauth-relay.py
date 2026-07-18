#!/usr/bin/env python3
"""
Minimal GitHub OAuth relay for Sveltia / Decap CMS "Sign In with GitHub".

Implements the two endpoints the CMS popup flow needs:
  GET /auth      -> redirect the user to GitHub's authorize page
  GET /callback  -> exchange the returned code for a token and hand it to the
                    CMS popup via window.postMessage

Standard library only (no third-party dependencies). CSRF-protected with a
short-lived, HttpOnly state cookie. Configuration comes from the environment
(see /etc/nharc-oauth.env):

  GITHUB_CLIENT_ID      OAuth App client id
  GITHUB_CLIENT_SECRET  OAuth App client secret
  OAUTH_SCOPE           GitHub scope to request (default: public_repo)
  REDIRECT_URI          must equal the OAuth App's Authorization callback URL
  ALLOWED_ORIGIN        the CMS origin allowed to receive the token
  PORT                  local listen port (default: 8402)
"""
import http.cookies
import http.server
import json
import os
import secrets
import socketserver
import urllib.parse
import urllib.request

CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET", "")
SCOPE = os.environ.get("OAUTH_SCOPE", "public_repo")
REDIRECT_URI = os.environ.get("REDIRECT_URI", "https://newweb.nharc.org/callback")
ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "https://newweb.nharc.org")
PORT = int(os.environ.get("PORT", "8402"))

GH_AUTHORIZE = "https://github.com/login/oauth/authorize"
GH_TOKEN = "https://github.com/login/oauth/access_token"


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
            return self._finish_auth(query)
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
