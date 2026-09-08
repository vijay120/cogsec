"""SQLite persistence for the CogSec tracker.

One local file (cogsec.db) holds everything. Tables are created on first run.
The data never leaves this machine and is git-ignored.
"""

import os
import sqlite3
from datetime import date, datetime, timedelta

DB_PATH = os.environ.get(
    "COGSEC_DB", os.path.join(os.path.dirname(__file__), "cogsec.db")
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_log (
    id                INTEGER PRIMARY KEY,
    log_date          TEXT UNIQUE NOT NULL,
    -- morning
    sleep_hours       REAL,
    no_phone_am       INTEGER DEFAULT 0,
    intentions        TEXT,
    exercise          INTEGER DEFAULT 0,
    meditation        INTEGER DEFAULT 0,
    -- during the day
    deep_work_blocks  INTEGER DEFAULT 0,
    phone_away_focus  INTEGER DEFAULT 0,
    post_block_reward INTEGER DEFAULT 0,
    metacog_thought   INTEGER DEFAULT 0,
    metacog_emotion   INTEGER DEFAULT 0,
    impl_intention    INTEGER DEFAULT 0,
    -- evening
    gratitude         TEXT,
    eve_worked        TEXT,
    eve_didnt         TEXT,
    eve_differently   TEXT,
    tomorrow_priority TEXT,
    phone_away_pm     INTEGER DEFAULT 0,
    screens_off       INTEGER DEFAULT 0,
    mood              INTEGER,
    score             INTEGER,
    notes             TEXT,
    created_at        TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS cbt_entry (
    id                INTEGER PRIMARY KEY,
    entry_date        TEXT NOT NULL,
    situation         TEXT,
    automatic_thought TEXT,
    distortion        TEXT,
    balanced_thought  TEXT,
    mood_before       INTEGER,
    mood_after        INTEGER,
    created_at        TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS urge_log (
    id         INTEGER PRIMARY KEY,
    logged_at  TEXT NOT NULL,
    log_date   TEXT NOT NULL,
    trigger    TEXT,
    feeling    TEXT,
    intensity  INTEGER,
    outcome    TEXT,
    notes      TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS weekly_review (
    id             INTEGER PRIMARY KEY,
    week_start     TEXT UNIQUE NOT NULL,
    what_worked    TEXT,
    what_didnt     TEXT,
    differently    TEXT,
    top_distortion TEXT,
    top_trigger    TEXT,
    score          INTEGER,
    created_at     TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# Columns added after v1 — kept in sync for existing databases via migrate().
DAILY_COLUMNS_V2 = [
    ("intentions", "TEXT"),
    ("phone_away_focus", "INTEGER DEFAULT 0"),
    ("post_block_reward", "INTEGER DEFAULT 0"),
    ("metacog_thought", "INTEGER DEFAULT 0"),
    ("metacog_emotion", "INTEGER DEFAULT 0"),
    ("impl_intention", "INTEGER DEFAULT 0"),
    ("eve_worked", "TEXT"),
    ("eve_didnt", "TEXT"),
    ("eve_differently", "TEXT"),
    ("tomorrow_priority", "TEXT"),
]


def init_db():
    with get_db() as conn:
        conn.executescript(SCHEMA)
        # Add any columns missing from a pre-existing database (safe no-op on new ones).
        have = {r["name"] for r in conn.execute("PRAGMA table_info(daily_log)")}
        for col, ddl in DAILY_COLUMNS_V2:
            if col not in have:
                conn.execute(f"ALTER TABLE daily_log ADD COLUMN {col} {ddl}")


# --------------------------------------------------------------------------
# Writes
# --------------------------------------------------------------------------

def upsert_daily(data):
    """Insert or replace the daily log for its date (one row per day)."""
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO daily_log
              (log_date, sleep_hours, no_phone_am, intentions, exercise, meditation,
               deep_work_blocks, phone_away_focus, post_block_reward,
               metacog_thought, metacog_emotion, impl_intention,
               gratitude, eve_worked, eve_didnt, eve_differently, tomorrow_priority,
               phone_away_pm, screens_off, mood, score, notes)
            VALUES
              (:log_date, :sleep_hours, :no_phone_am, :intentions, :exercise, :meditation,
               :deep_work_blocks, :phone_away_focus, :post_block_reward,
               :metacog_thought, :metacog_emotion, :impl_intention,
               :gratitude, :eve_worked, :eve_didnt, :eve_differently, :tomorrow_priority,
               :phone_away_pm, :screens_off, :mood, :score, :notes)
            ON CONFLICT(log_date) DO UPDATE SET
               sleep_hours=excluded.sleep_hours,
               no_phone_am=excluded.no_phone_am,
               intentions=excluded.intentions,
               exercise=excluded.exercise,
               meditation=excluded.meditation,
               deep_work_blocks=excluded.deep_work_blocks,
               phone_away_focus=excluded.phone_away_focus,
               post_block_reward=excluded.post_block_reward,
               metacog_thought=excluded.metacog_thought,
               metacog_emotion=excluded.metacog_emotion,
               impl_intention=excluded.impl_intention,
               gratitude=excluded.gratitude,
               eve_worked=excluded.eve_worked,
               eve_didnt=excluded.eve_didnt,
               eve_differently=excluded.eve_differently,
               tomorrow_priority=excluded.tomorrow_priority,
               phone_away_pm=excluded.phone_away_pm,
               screens_off=excluded.screens_off,
               mood=excluded.mood,
               score=excluded.score,
               notes=excluded.notes
            """,
            data,
        )


def insert_cbt(data):
    with get_db() as conn:
        conn.execute(
            """INSERT INTO cbt_entry
               (entry_date, situation, automatic_thought, distortion,
                balanced_thought, mood_before, mood_after)
               VALUES (:entry_date, :situation, :automatic_thought, :distortion,
                       :balanced_thought, :mood_before, :mood_after)""",
            data,
        )


def insert_urge(data):
    with get_db() as conn:
        conn.execute(
            """INSERT INTO urge_log
               (logged_at, log_date, trigger, feeling, intensity, outcome, notes)
               VALUES (:logged_at, :log_date, :trigger, :feeling, :intensity,
                       :outcome, :notes)""",
            data,
        )


def upsert_weekly(data):
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO weekly_review
              (week_start, what_worked, what_didnt, differently,
               top_distortion, top_trigger, score)
            VALUES
              (:week_start, :what_worked, :what_didnt, :differently,
               :top_distortion, :top_trigger, :score)
            ON CONFLICT(week_start) DO UPDATE SET
               what_worked=excluded.what_worked,
               what_didnt=excluded.what_didnt,
               differently=excluded.differently,
               top_distortion=excluded.top_distortion,
               top_trigger=excluded.top_trigger,
               score=excluded.score
            """,
            data,
        )


def delete_row(table, row_id):
    allowed = {"daily_log", "cbt_entry", "urge_log", "weekly_review"}
    if table not in allowed:
        raise ValueError("unknown table")
    with get_db() as conn:
        conn.execute(f"DELETE FROM {table} WHERE id = ?", (row_id,))


# --------------------------------------------------------------------------
# Reads — recent entries
# --------------------------------------------------------------------------

def get_daily(log_date):
    with get_db() as conn:
        return conn.execute(
            "SELECT * FROM daily_log WHERE log_date = ?", (log_date,)
        ).fetchone()


def recent(table, limit=20):
    order = {
        "daily_log": "log_date DESC",
        "cbt_entry": "entry_date DESC, id DESC",
        "urge_log": "logged_at DESC",
        "weekly_review": "week_start DESC",
    }[table]
    with get_db() as conn:
        return conn.execute(
            f"SELECT * FROM {table} ORDER BY {order} LIMIT ?", (limit,)
        ).fetchall()


# --------------------------------------------------------------------------
# Reads — analytics for the dashboard
# --------------------------------------------------------------------------

def daily_scores(days=30):
    """(date, score) for the last `days` days, filling gaps with None."""
    today = date.today()
    with get_db() as conn:
        rows = {
            r["log_date"]: r["score"]
            for r in conn.execute(
                "SELECT log_date, score FROM daily_log WHERE log_date >= ?",
                ((today - timedelta(days=days - 1)).isoformat(),),
            ).fetchall()
        }
    out = []
    for i in range(days - 1, -1, -1):
        d = (today - timedelta(days=i)).isoformat()
        out.append((d, rows.get(d)))
    return out


def adherence(days=30):
    since = (date.today() - timedelta(days=days - 1)).isoformat()
    with get_db() as conn:
        row = conn.execute(
            """SELECT
                 COUNT(*) AS n,
                 SUM(exercise) AS exercise,
                 SUM(meditation) AS meditation,
                 SUM(no_phone_am) AS no_phone_am,
                 AVG(sleep_hours) AS avg_sleep
               FROM daily_log WHERE log_date >= ?""",
            (since,),
        ).fetchone()
    n = row["n"] or 0
    pct = lambda v: round(100 * (v or 0) / n) if n else 0
    return {
        "days_logged": n,
        "exercise_pct": pct(row["exercise"]),
        "meditation_pct": pct(row["meditation"]),
        "no_phone_pct": pct(row["no_phone_am"]),
        "avg_sleep": round(row["avg_sleep"], 1) if row["avg_sleep"] else None,
    }


def _week_start(d):
    return d - timedelta(days=d.weekday())  # Monday


def urge_weekly(weeks=8):
    """Per-week (label, count, avg_intensity) for the last `weeks` weeks."""
    start = _week_start(date.today()) - timedelta(weeks=weeks - 1)
    with get_db() as conn:
        rows = conn.execute(
            "SELECT log_date, intensity FROM urge_log WHERE log_date >= ?",
            (start.isoformat(),),
        ).fetchall()
    buckets = {}
    for r in rows:
        try:
            d = date.fromisoformat(r["log_date"][:10])
        except ValueError:
            continue
        ws = _week_start(d).isoformat()
        buckets.setdefault(ws, []).append(r["intensity"] or 0)
    out = []
    for i in range(weeks - 1, -1, -1):
        ws = (_week_start(date.today()) - timedelta(weeks=i)).isoformat()
        vals = buckets.get(ws, [])
        avg = round(sum(vals) / len(vals), 1) if vals else 0
        out.append({"week": ws[5:], "count": len(vals), "avg_intensity": avg})
    return out


def days_since_last_slip():
    """Days since the most recent 'acted' urge (the extinction/abstinence streak)."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT MAX(log_date) AS d FROM urge_log WHERE outcome = 'acted'"
        ).fetchone()
        first = conn.execute(
            "SELECT MIN(log_date) AS d FROM urge_log"
        ).fetchone()
    ref = row["d"] or first["d"]
    if not ref:
        return None
    try:
        return (date.today() - date.fromisoformat(ref[:10])).days
    except ValueError:
        return None


def daily_streak():
    """Consecutive days up to today with a daily_log entry."""
    with get_db() as conn:
        dates = {
            r["log_date"]
            for r in conn.execute("SELECT log_date FROM daily_log").fetchall()
        }
    streak, d = 0, date.today()
    while d.isoformat() in dates:
        streak += 1
        d -= timedelta(days=1)
    return streak


def top_distortions(limit=5):
    with get_db() as conn:
        return conn.execute(
            """SELECT distortion, COUNT(*) AS n
               FROM cbt_entry
               WHERE distortion IS NOT NULL AND distortion <> ''
               GROUP BY distortion ORDER BY n DESC LIMIT ?""",
            (limit,),
        ).fetchall()


def urge_outcomes():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT outcome, COUNT(*) AS n FROM urge_log GROUP BY outcome"
        ).fetchall()
    return {r["outcome"]: r["n"] for r in rows}
