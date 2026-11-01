'''
The web. It checks board orders and keeps nothing about them: requests are
answered and forgotten. Saved orders only live in the browser of each user.
'''
import hmac
import os
import secrets
from datetime import timedelta
from functools import wraps
from pathlib import Path

from flask import (
    Flask,
    abort,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.middleware.proxy_fix import ProxyFix

from web.accounts import MIN_PASSWORD, AccountError, Accounts
from web.i18n import DEFAULT_LANGUAGE, LANGUAGES, browser_texts, text
from web.lists import PlayerList
from web.rosters import load_rosters
from web.rules import DEFAULT_MARGIN, check_order

DEVICE_COOKIE = "elo_device"
LANGUAGE_COOKIE = "elo_lang"
MAX_PLAYERS = 30
YEAR = 365 * 24 * 3600


def limit_key():
    return session.get("user_id") or get_remote_address()


limiter = Limiter(key_func=limit_key, storage_uri="memory://")


def create_app(config=None):
    folder = os.environ.get("ELO_DATA", "data")
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=Path(os.environ["ELO_SECRET_FILE"]).read_text(encoding="utf-8").strip()
        if "ELO_SECRET_FILE" in os.environ else secrets.token_hex(32),
        SESSION_COOKIE_NAME="elo_session",
        SESSION_COOKIE_PATH=os.environ.get("ELO_COOKIE_PATH", "/elo/"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=timedelta(days=30),
        MAX_CONTENT_LENGTH=16 * 1024,
        MARGIN=int(os.environ.get("ELO_MARGIN", DEFAULT_MARGIN)))
    app.config.update(config or {})
    if "ACCOUNTS" not in app.config:
        app.config["ACCOUNTS"] = Accounts(Path(folder) / "accounts.db")
    if "DATA_FOLDER" not in app.config:
        app.config["DATA_FOLDER"] = folder
    if "PLAYERS" not in app.config:
        app.config["PLAYERS"] = PlayerList(folder, os.environ.get("ELO_LIST"))
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_prefix=1)
    limiter.init_app(app)
    accounts, players = app.config["ACCOUNTS"], app.config["PLAYERS"]

    @app.before_request
    def load_user():
        g.user = None
        language = request.cookies.get(LANGUAGE_COOKIE)
        g.language = language if language in LANGUAGES else DEFAULT_LANGUAGE
        device = request.cookies.get(DEVICE_COOKIE)
        #The device must still exist in every request: removing it closes the session
        user = accounts.user_of_device(device)
        if user and session.get("user_id") == user["id"]:
            g.user = user
        if request.method == "POST":
            sent = request.headers.get("X-CSRF") or request.form.get("csrf", "")
            if not hmac.compare_digest(sent.encode(), session.get("csrf", "-").encode()):
                abort(403)

    @app.context_processor
    def template_values():
        return {"csrf": csrf_token(), "user": g.user, "language": g.language, "languages": LANGUAGES,
                "t": lambda key, **values: text(g.language, key, **values)}

    @app.after_request
    def security_headers(response):
        response.headers.update({
            "Content-Security-Policy": "default-src 'self'; frame-ancestors 'none'; base-uri 'none'"
                                       "; form-action 'self'",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "no-referrer",
            "X-Robots-Tag": "noindex, nofollow",
            "Cache-Control": "no-store"})
        return response

    def set_device(response, token):
        response.set_cookie(DEVICE_COOKIE, token, max_age=YEAR, secure=app.config["SESSION_COOKIE_SECURE"],
                            httponly=True, samesite="Lax", path=app.config["SESSION_COOKIE_PATH"])
        return response

    def start_session(user):
        session.clear()
        session.permanent = True
        session["user_id"] = user["id"]

    @app.get("/")
    @login_required
    def index():
        return render_template("tool.html", list_label=players.label(g.language),
                               browser_texts=browser_texts(g.language))

    @app.route("/login", methods=["GET", "POST"])
    @limiter.limit("10 per minute", methods=["POST"], key_func=get_remote_address)
    def login():
        known = accounts.user_of_device(request.cookies.get(DEVICE_COOKIE))
        if request.method == "POST":
            user = accounts.login(request.cookies.get(DEVICE_COOKIE),
                                  request.form.get("password", ""))
            if user:
                start_session(user)
                #Renews the year of the device
                return set_device(redirect(url_for("index")), request.cookies[DEVICE_COOKIE])
            flash(text(g.language, "wrong_password"))
        return render_template("login.html", known=known)

    @app.post("/logout")
    def logout():
        session.clear()
        return redirect(url_for("login"))

    @app.route("/invite/<token>", methods=["GET", "POST"])
    @limiter.limit("10 per minute", methods=["POST"], key_func=get_remote_address)
    def invite(token):
        user = accounts.find_invite(token)
        if user is None:
            return render_template("message.html", title=text(g.language, "invite_used_title"),
                                   message=text(g.language, "invite_used_text")), 404
        if request.method == "POST":
            try:
                user, device_token = accounts.accept_invite(token, request.form.get("password", ""))
            except AccountError as error:
                flash(text(g.language, error.key, **error.values))
            else:
                start_session(user)
                return set_device(redirect(url_for("index")), device_token)
        return render_template("invite.html", invited=user, min_password=MIN_PASSWORD)

    @app.post("/language")
    def language():
        '''
        Remembers the language. It stays on the same page, and only inside the site
        '''
        chosen = request.form.get("lang")
        target = request.form.get("next", "")
        root = request.script_root + "/"
        if not target.startswith(root) or target.startswith("//") or "\\" in target:
            target = url_for("index")
        response = redirect(target)
        if chosen in LANGUAGES:
            response.set_cookie(LANGUAGE_COOKIE, chosen, max_age=YEAR, httponly=True,
                                secure=app.config["SESSION_COOKIE_SECURE"], samesite="Lax",
                                path=app.config["SESSION_COOKIE_PATH"])
        return response

    @app.get("/privacidad")
    def privacy():
        return render_template("privacy.html")

    @app.post("/api/search")
    @login_required
    @limiter.limit("30 per minute")
    def search():
        results, more = players.search(str(json_body().get("text", ""))[:80])
        return jsonify(results=results, more=more)

    @app.post("/api/lookup")
    @login_required
    @limiter.limit("30 per minute")
    def lookup():
        ids = valid_ids(json_body().get("ids"))
        found = players.get(ids)
        return jsonify(players=list(found.values()),
                       missing=[fide_id for fide_id in ids if fide_id not in found])

    @app.post("/api/roster")
    @login_required
    @limiter.limit("30 per minute")
    def roster():
        '''
        Last season's players of the club of the user, and of no other club
        '''
        season, rosters = load_rosters(app.config["DATA_FOLDER"])
        found = players.get(rosters.get(g.user["club"], []))
        ordered = sorted(found.values(), key=lambda player: (player["rating"] is None,
                                                             -(player["rating"] or 0), player["name"]))
        return jsonify(season=season, players=ordered)

    @app.post("/api/check")
    @login_required
    @limiter.limit("60 per minute")
    def check():
        '''
        Each entry is a FIDE ID, or null for a player without one
        '''
        entries = json_body().get("entries")
        if not isinstance(entries, list) or len(entries) > MAX_PLAYERS:
            abort(400)
        found = players.get(valid_ids([entry for entry in entries if entry is not None]))
        ratings = [found.get(entry, {}).get("rating") for entry in entries]
        return jsonify(errors=check_order(ratings, app.config["MARGIN"]), ratings=ratings,
                       list=players.label(g.language))

    @app.get("/admin")
    @admin_required
    def admin():
        return render_template("admin.html", users=accounts.list_users(),
                               clubs=accounts.free_clubs(), link=session.pop("invite_link", None))

    @app.post("/admin/invite")
    @admin_required
    def admin_invite():
        try:
            user_id = request.form.get("user_id", type=int)
            if user_id:
                token = accounts.create_invite(user_id=user_id)
            elif request.form.get("name", "").strip():
                token = accounts.create_invite(request.form["name"], request.form.get("club"))
            else:
                raise AccountError("name_missing")
            session["invite_link"] = url_for("invite", token=token, _external=True)
        except AccountError as error:
            flash(text(g.language, error.key, **error.values))
        return redirect(url_for("admin"))

    @app.post("/admin/devices/<int:user_id>")
    @admin_required
    def admin_devices(user_id):
        accounts.remove_devices(user_id)
        return redirect(url_for("admin"))

    @app.post("/admin/delete/<int:user_id>")
    @admin_required
    def admin_delete(user_id):
        try:
            accounts.delete_user(user_id)
        except AccountError as error:
            flash(text(g.language, error.key, **error.values))
        return redirect(url_for("admin"))

    return app


def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(16)
    return session["csrf"]


def json_body():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        abort(400)
    return body


def valid_ids(ids):
    if not isinstance(ids, list) or len(ids) > MAX_PLAYERS:
        abort(400)
    if not all(isinstance(fide_id, int) and not isinstance(fide_id, bool) for fide_id in ids):
        abort(400)
    return ids


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if g.user is None:
            if request.path.startswith("/api/"):
                abort(401)
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapper


def admin_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("login"))
        if not g.user["is_admin"]:
            abort(403)
        return view(*args, **kwargs)
    return wrapper
