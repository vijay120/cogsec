"""CogSec Tracker — a single-user practice tracker.

Run locally:  python app/server.py   (or ./app/start)  → http://127.0.0.1:8765
Deployed:     gunicorn serves this module; see app/README.md.

Data lives in the SQLite file at $COGSEC_DB (defaults to app/cogsec.db, which is
git-ignored). Locally that's your machine; deployed it's the mounted volume.

Auth: set $COGSEC_PASSCODE to put every page behind a passcode. Unset means no
gate, which is fine on 127.0.0.1 and never fine on a public URL — so when
$COGSEC_REQUIRE_AUTH is set (the deployed config does), booting without a
passcode is a hard error rather than a silently open journal.
"""

import hmac
import os
import secrets
import threading
import time
import webbrowser
from datetime import date, datetime, timedelta

from flask import (
    Flask, redirect, render_template, request, send_from_directory, session,
    url_for,
)
from markupsafe import Markup

import charts
import db

app = Flask(__name__)
app.config["TEMPLATES_AUTO_RELOAD"] = True  # pick up template edits without a restart

# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------

PASSCODE = os.environ.get("COGSEC_PASSCODE", "")
REQUIRE_AUTH = bool(os.environ.get("COGSEC_REQUIRE_AUTH"))

if REQUIRE_AUTH and not PASSCODE:
    raise SystemExit(
        "COGSEC_REQUIRE_AUTH is set but COGSEC_PASSCODE is empty — refusing to "
        "start an unauthenticated server. Run: fly secrets set COGSEC_PASSCODE=…"
    )

# A stable key keeps you logged in across restarts and deploys. Without one we
# generate a throwaway (local dev), which just means re-logging in on restart.
app.secret_key = os.environ.get("COGSEC_SECRET_KEY") or secrets.token_hex(32)
app.config.update(
    PERMANENT_SESSION_LIFETIME=timedelta(days=365),  # a home-screen app shouldn't
    SESSION_COOKIE_HTTPONLY=True,                    # log you out every week
    SESSION_COOKIE_SAMESITE="Lax",   # also our CSRF defence: cross-site POSTs
    SESSION_COOKIE_SECURE=REQUIRE_AUTH,              # send no cookie at all
)

# Public URLs get scanned. Throttle guesses per-process; one machine, so a dict
# is enough — no need for shared state.
_FAILURES = {}
_MAX_FAILURES = 8
_LOCKOUT_SECONDS = 900

# Reachable without a session: the login flow itself, and the assets iOS needs
# to fetch before you're logged in (icons, manifest, service worker).
_PUBLIC_ENDPOINTS = {"login", "static", "manifest", "service_worker", "favicon",
                     "apple_touch_icon", "healthz"}


def _client_key():
    """Fly puts the real client IP in Fly-Client-IP; fall back to the socket."""
    return request.headers.get("Fly-Client-IP") or request.remote_addr or "?"


def _locked_out(key):
    fails, until = _FAILURES.get(key, (0, 0.0))
    return fails >= _MAX_FAILURES and time.time() < until


@app.before_request
def require_login():
    if not PASSCODE:                       # local, no gate
        return None
    if request.endpoint in _PUBLIC_ENDPOINTS:
        return None
    if session.get("auth"):
        return None
    # full_path always tacks on a "?"; drop it so the round-trip URL stays clean.
    dest = request.full_path.rstrip("?") if request.method == "GET" else None
    return redirect(url_for("login", next=dest))


@app.route("/login", methods=["GET", "POST"])
def login():
    if not PASSCODE or session.get("auth"):
        return redirect(url_for("dashboard"))

    error = None
    key = _client_key()
    if request.method == "POST":
        if _locked_out(key):
            error = "Too many attempts. Try again later."
        elif hmac.compare_digest(request.form.get("passcode", ""), PASSCODE):
            _FAILURES.pop(key, None)
            session.clear()
            session["auth"] = True
            session.permanent = True
            dest = request.args.get("next") or ""
            # Only ever redirect to a path on this site, never an absolute URL.
            return redirect(dest if dest.startswith("/") and not dest.startswith("//")
                            else url_for("dashboard"))
        else:
            fails = _FAILURES.get(key, (0, 0.0))[0] + 1
            _FAILURES[key] = (fails, time.time() + _LOCKOUT_SECONDS)
            error = "Incorrect passcode."
    return render_template("login.html", error=error), (401 if error else 200)


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.template_global()
def auth_enabled():
    return bool(PASSCODE)


# --------------------------------------------------------------------------
# PWA plumbing — these must live at the root, not under /static:
# a service worker can only control paths at or below its own URL.
# --------------------------------------------------------------------------

_ICONS = os.path.join(os.path.dirname(__file__), "static", "icons")


@app.route("/sw.js")
def service_worker():
    resp = send_from_directory(app.static_folder, "sw.js", mimetype="application/javascript")
    resp.headers["Cache-Control"] = "no-cache"  # always re-check for a new worker
    return resp


@app.route("/manifest.webmanifest")
def manifest():
    return send_from_directory(app.static_folder, "manifest.webmanifest",
                               mimetype="application/manifest+json")


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(_ICONS, "favicon.ico")


@app.route("/apple-touch-icon.png")
def apple_touch_icon():
    return send_from_directory(_ICONS, "apple-touch-icon.png")


@app.route("/healthz")
def healthz():
    return {"ok": True}


@app.template_global()
def delete_btn(table, row_id):
    return Markup(
        f'<form method="post" action="/delete/{table}/{row_id}" class="del" '
        "onsubmit=\"return confirm('Delete this entry?')\">"
        '<button class="link" title="Delete">✕</button></form>'
    )

DISTORTIONS = [
    "Catastrophizing", "All-or-nothing", "Mind reading", "Overgeneralization",
    "Emotional reasoning", "Should statements", "Discounting positives",
    "Personalization", "Fortune telling", "Labeling",
]
URGE_TRIGGERS = [
    "Post-nap (sleep inertia)", "Alone / unstructured time", "Browsing / image",
    "In bed with phone", "Stress", "Boredom", "Other",
]
URGE_FEELINGS = [
    "Restless / tense", "Bored", "Lonely", "Tired", "Hungry", "Angry",
    "Anxious / stressed", "Genuine desire", "Other",
]
OUTCOMES = ["surfed", "redirected", "acted"]


def _int(name, default=None):
    v = request.form.get(name)
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _float(name, default=None):
    v = request.form.get(name)
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _bool(name):
    return 1 if request.form.get(name) else 0


DAILY_MAX = 16  # number of items counted below


def compute_daily_score(f):
    """Score = count of completed checklist items (out of DAILY_MAX). No weights."""
    def filled(*keys):
        return any((f.get(k) or "").strip() for k in keys)

    items = [
        (f.get("sleep_hours") or 0) >= 7,        # morning
        f.get("no_phone_am"),
        filled("intentions"),
        f.get("exercise"),
        f.get("meditation"),
        (f.get("deep_work_blocks") or 0) >= 1,   # during the day
        f.get("phone_away_focus"),
        f.get("post_block_reward"),
        f.get("metacog_thought"),
        f.get("metacog_emotion"),
        f.get("impl_intention"),
        filled("gratitude"),                     # evening
        filled("eve_worked", "eve_didnt", "eve_differently"),
        filled("tomorrow_priority"),
        f.get("phone_away_pm"),
        f.get("screens_off"),
    ]
    return sum(1 for i in items if i)


@app.template_global()
def score_band(score):
    """Map a daily score to the wiki's band label."""
    if score is None:
        return ""
    if score >= 12:
        return "Excellent"
    if score >= 8:
        return "Good"
    if score >= 4:
        return "Partial"
    return "Reset"


@app.route("/")
def dashboard():
    scores = db.daily_scores(30)
    weekly = db.urge_weekly(8)
    distortions = db.top_distortions(5)

    score_svg = charts.sparkline(scores, color=charts.TEAL, fixed_max=DAILY_MAX)
    freq_svg = charts.bars(
        [{"label": w["week"], "value": w["count"]} for w in weekly],
        color=charts.AMBER,
    )
    intensity_svg = charts.sparkline(
        [(w["week"], w["avg_intensity"] or None) for w in weekly],
        color=charts.AMBER, fixed_max=10,
    )
    distortion_svg = charts.hbars(
        [(r["distortion"], r["n"]) for r in distortions], color=charts.TEAL
    )
    return render_template(
        "dashboard.html",
        active="dashboard",
        adherence=db.adherence(30),
        streak=db.days_since_last_slip(),
        log_streak=db.daily_streak(),
        outcomes=db.urge_outcomes(),
        score_svg=score_svg,
        freq_svg=freq_svg,
        intensity_svg=intensity_svg,
        distortion_svg=distortion_svg,
    )


@app.route("/daily", methods=["GET", "POST"])
def daily():
    if request.method == "POST":
        g = lambda k: request.form.get(k, "").strip()
        f = {
            "log_date": request.form.get("log_date") or date.today().isoformat(),
            # morning
            "sleep_hours": _float("sleep_hours"),
            "no_phone_am": _bool("no_phone_am"),
            "intentions": g("intentions"),
            "exercise": _bool("exercise"),
            "meditation": _bool("meditation"),
            # during the day
            "deep_work_blocks": _int("deep_work_blocks", 0),
            "phone_away_focus": _bool("phone_away_focus"),
            "post_block_reward": _bool("post_block_reward"),
            "metacog_thought": _bool("metacog_thought"),
            "metacog_emotion": _bool("metacog_emotion"),
            "impl_intention": _bool("impl_intention"),
            # evening
            "gratitude": g("gratitude"),
            "eve_worked": g("eve_worked"),
            "eve_didnt": g("eve_didnt"),
            "eve_differently": g("eve_differently"),
            "tomorrow_priority": g("tomorrow_priority"),
            "phone_away_pm": _bool("phone_away_pm"),
            "screens_off": _bool("screens_off"),
            "mood": _int("mood"),
            "notes": g("notes"),
        }
        f["score"] = compute_daily_score(f)
        db.upsert_daily(f)
        # stay on the day just saved (not today), so it doesn't snap back
        return redirect(url_for("daily", date=f["log_date"]))
    sel_date = request.args.get("date") or date.today().isoformat()
    return render_template(
        "daily.html", active="daily", sel_date=sel_date,
        cur=db.get_daily(sel_date), entries=db.recent("daily_log", 21),
        daily_max=DAILY_MAX,
    )


@app.route("/cbt", methods=["GET", "POST"])
def cbt():
    if request.method == "POST":
        db.insert_cbt({
            "entry_date": request.form.get("entry_date") or date.today().isoformat(),
            "situation": request.form.get("situation", "").strip(),
            "automatic_thought": request.form.get("automatic_thought", "").strip(),
            "distortion": request.form.get("distortion", ""),
            "balanced_thought": request.form.get("balanced_thought", "").strip(),
            "mood_before": _int("mood_before"),
            "mood_after": _int("mood_after"),
        })
        return redirect(url_for("cbt"))
    return render_template(
        "cbt.html", active="cbt", today=date.today().isoformat(),
        distortions=DISTORTIONS, entries=db.recent("cbt_entry", 15),
    )


@app.route("/urge", methods=["GET", "POST"])
def urge():
    if request.method == "POST":
        now = datetime.now().replace(microsecond=0)
        logged_at = request.form.get("logged_at") or now.isoformat(timespec="minutes")
        db.insert_urge({
            "logged_at": logged_at,
            "log_date": logged_at[:10],
            "trigger": request.form.get("trigger", ""),
            "feeling": request.form.get("feeling", ""),
            "intensity": _int("intensity"),
            "outcome": request.form.get("outcome", ""),
            "notes": request.form.get("notes", "").strip(),
        })
        return redirect(url_for("urge"))
    return render_template(
        "urge.html", active="urge",
        now=datetime.now().strftime("%Y-%m-%dT%H:%M"),
        triggers=URGE_TRIGGERS, feelings=URGE_FEELINGS, outcomes=OUTCOMES,
        entries=db.recent("urge_log", 20),
    )


@app.route("/weekly", methods=["GET", "POST"])
def weekly():
    if request.method == "POST":
        db.upsert_weekly({
            "week_start": request.form.get("week_start"),
            "what_worked": request.form.get("what_worked", "").strip(),
            "what_didnt": request.form.get("what_didnt", "").strip(),
            "differently": request.form.get("differently", "").strip(),
            "top_distortion": request.form.get("top_distortion", ""),
            "top_trigger": request.form.get("top_trigger", ""),
            "score": _int("score"),
        })
        return redirect(url_for("weekly"))
    today = date.today()
    monday = today.fromordinal(today.toordinal() - today.weekday())
    return render_template(
        "weekly.html", active="weekly", monday=monday.isoformat(),
        distortions=DISTORTIONS, triggers=URGE_TRIGGERS,
        entries=db.recent("weekly_review", 12),
    )


@app.route("/delete/<table>/<int:row_id>", methods=["POST"])
def delete(table, row_id):
    db.delete_row(table, row_id)
    return redirect(request.referrer or url_for("dashboard"))


def _open_browser():
    webbrowser.open("http://127.0.0.1:8765")


# At import, not under __main__: gunicorn imports this module and never runs
# __main__, so the schema has to be ensured here or a fresh volume stays empty.
db.init_db()


if __name__ == "__main__":
    if not os.environ.get("COGSEC_NO_BROWSER"):
        threading.Timer(0.8, _open_browser).start()
    app.run(host="127.0.0.1", port=8765, debug=False)
