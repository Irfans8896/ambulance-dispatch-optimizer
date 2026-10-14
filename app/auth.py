"""Login, roles (admin / dispatcher / driver) and the permission rules for every endpoint."""
import re

from flask import (Blueprint, current_app, jsonify, redirect, render_template, request, session, url_for)
from werkzeug.security import check_password_hash

from .db import get_db

bp = Blueprint("auth", __name__)

ADMIN, DISPATCHER, DRIVER = "admin", "dispatcher", "driver"

# (method, path pattern, roles allowed). Anything not listed needs a login but no special role.
RULES = [
    ("POST", r"/api/incidents/dispatch", {ADMIN, DISPATCHER}),
    ("POST", r"/api/dispatches/\d+/advance", {ADMIN, DISPATCHER, DRIVER}),
    ("POST", r"/api/dispatches/\d+/progress", {ADMIN, DISPATCHER, DRIVER}),
    ("POST", r"/api/dispatches/\d+/severity", {ADMIN, DISPATCHER, DRIVER}),
    ("POST", r"/api/dispatches/\d+/hospital", {ADMIN, DISPATCHER, DRIVER}),
    ("GET", r"/api/dispatches/\d+/hospital-options", {ADMIN, DISPATCHER, DRIVER}),
    ("POST", r"/api/dispatches/recheck", {ADMIN, DISPATCHER}),
    ("POST", r"/api/settings/auto-traffic", {ADMIN}),
    ("POST", r"/api/demo/simulate", {ADMIN}),
    ("GET", r"/api/queue", {ADMIN, DISPATCHER}),
    ("GET", r"/api/analytics", {ADMIN, DISPATCHER}),
    ("GET", r"/analytics", {ADMIN, DISPATCHER}),
    ("POST", r"/api/roads/traffic", {ADMIN}),
    ("POST", r"/api/ambulances", {ADMIN}),
    ("POST", r"/api/hospitals", {ADMIN}),
    ("POST", r"/api/hospitals/\d+", {ADMIN}),
    ("GET", r"/api/hotspots", {ADMIN, DISPATCHER}),
    ("GET", r"/api/prepositioning", {ADMIN, DISPATCHER}),
    ("GET", r"/hotspot-map", {ADMIN, DISPATCHER}),
    ("GET", r"/api/reports/.*", {ADMIN, DISPATCHER}),
    ("GET", r"/api/traffic-history", {ADMIN, DISPATCHER}),
]
PUBLIC = {"/login", "/health", "/driver"}


def current_user():
    if not current_app.config.get("AUTH_REQUIRED", True):
        return {"username": "demo (login disabled)", "role": ADMIN, "ambulance_id": None}
    return session.get("user")


@bp.before_app_request
def guard():
    if not current_app.config.get("AUTH_REQUIRED", True):
        return None
    path = request.path
    if path in PUBLIC or path.startswith("/static/"):
        return None
    user = session.get("user")
    if not user:
        if path.startswith("/api/"):
            return jsonify({"error": "Login required"}), 401
        return redirect(url_for("auth.login", next=path))
    for method, pattern, roles in RULES:
        if method == request.method and re.fullmatch(pattern, path):
            if user["role"] not in roles:
                return jsonify({"error": "Your role (%s) is not allowed to do this" % user["role"]}), 403
            break
    m = re.fullmatch(r"/api/dispatches/(\d+)/(?:advance|progress|severity|hospital|hospital-options)", path)
    if m and user["role"] == DRIVER:      # drivers only move and manage their own trip
        row = get_db().execute("SELECT ambulance_id FROM dispatches WHERE dispatch_id=?", (int(m.group(1)),)).fetchone()
        if row is None or row["ambulance_id"] != user["ambulance_id"]:
            return jsonify({"error": "This dispatch is not assigned to your ambulance"}), 403
    return None


def _safe_next(target):
    return target if target and target.startswith("/") and not target.startswith("//") else "/"


@bp.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        name = (request.form.get("username") or "").strip()
        row = get_db().execute("SELECT * FROM users WHERE username=?", (name,)).fetchone()
        if row and check_password_hash(row["password_hash"], request.form.get("password") or ""):
            session.clear()
            session["user"] = {"username": row["username"], "role": row["role"], "ambulance_id": row["ambulance_id"]}
            return redirect(_safe_next(request.args.get("next")))
        error = "Wrong username or password"
    return render_template("login.html", error=error,
                           show_demo=current_app.config.get("SHOW_DEMO_LOGINS", True)), (401 if error else 200)


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


@bp.route("/api/me")
def me():
    user = current_user()
    return jsonify(user) if user else (jsonify({"error": "Login required"}), 401)
