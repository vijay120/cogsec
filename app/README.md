# CogSec Tracker

A single-user tracker for the practices in this wiki. Runs two ways:

- **Locally** — `./app/start`, data in `app/cogsec.db`, nothing leaves your machine.
- **On Fly.io** — reachable from your phone as a home-screen app, behind a passcode.

**The data is never committed.** `*.db` is git-ignored and `.dockerignore`d, so the
journal is never in a commit or an image layer. The code is shared; the data is not.

> **When it's deployed, the privacy story changes** and it's worth being honest about
> it: your entries sit on a Fly.io volume rather than only your laptop. They're behind
> a passcode and HTTPS, but Fly can technically access the disk. If that trade isn't
> one you want, run locally and reach it over [Tailscale](https://tailscale.com)
> instead — same PWA, no third party, but only while your Mac is awake.

---

## ▶️ Starting the server (e.g. after a computer restart)

1. Open the **Terminal** app.
2. Go to the project folder:
   ```bash
   cd /Users/vijay/cogsec
   ```
3. Start the tracker:
   ```bash
   ./app/start
   ```
4. It prints `CogSec Tracker → http://127.0.0.1:8765` and **opens that page in your
   browser automatically**. If it doesn't, just open <http://127.0.0.1:8765> yourself.

**Leave that Terminal window open while you use the app** — the links only work
while the server is running.

### Stopping it
Press **`Ctrl-C`** in the Terminal window (or just close the window). Your data is
already saved; stopping loses nothing.

### One-line version
Copy-paste this any time:
```bash
cd /Users/vijay/cogsec && ./app/start
```

> Nothing is lost on a computer restart. The `.venv` and your `app/cogsec.db`
> database both live on disk, so `./app/start` just picks up where you left off.
> (First run only: it auto-creates the `.venv` and installs Flask, which takes a
> few extra seconds.)

---

## Everyday use

- **Daily log — two touches a day.** Fill the morning part (sleep, habits, 3
  intentions) in the AM and save. In the evening, reopen it — your morning entries
  reload — add the reflection + tomorrow's #1 priority and save again.
- **Urge & CBT — ad hoc.** Log an urge the moment it happens; write a CBT
  reappraisal whenever something bothers you.
- **Weekly review — once a week**, any day you keep (Saturday/Sunday both fine).
- **Dashboard** shows your trends any time. The "How to use this" table lives there too.

### Score
Your daily score is simply **how many practices you did that day** — aim for **8+**
most days, not all 16. Skipping items is normal; a partial day still saves in full.
It's a consistency signal, not a grade.

---

## 📱 Putting it on your iPhone

Once deployed (below), install it as a home-screen app — no App Store, no TestFlight,
no developer account:

1. Open the app's URL **in Safari** (not Chrome — only Safari can install a real
   home-screen web app on iOS).
2. Log in with your passcode.
3. Tap **Share** → **Add to Home Screen** → **Add**.

You get an icon on the home screen that opens fullscreen with no browser chrome.
The passcode is remembered for a year, so it's normally a single tap to log an urge.

**What works offline:** pages you've already opened stay readable. **Saving does
not** — entries write straight to the server, so a save needs a connection. That's
deliberate: every form here is a last-write-wins upsert, so replaying queued offline
writes later would silently clobber whatever you'd logged in between.

---

## ☁️ Deploying to Fly.io

Roughly **$0.20–0.60/month**: the machine stops when idle and wakes on your next
request, so you pay for seconds used plus ~$0.15/mo of storage.

```bash
brew install flyctl
fly auth login

# App names are globally unique — pick your own and put it in fly.toml as `app = `.
fly apps create cogsec-<something-unique>

# Persistent disk for the SQLite file. Use the same region as fly.toml.
fly volumes create cogsec_data --region sjc --size 1 --yes

# Set BOTH before the first deploy. COGSEC_REQUIRE_AUTH=1 is in fly.toml, so a
# deploy without a passcode deliberately fails to boot rather than serving your
# journal to the open internet.
fly secrets set \
  COGSEC_PASSCODE='pick-a-long-passphrase' \
  COGSEC_SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"

fly deploy
fly open
```

`COGSEC_SECRET_KEY` signs the session cookie — keep it stable, or every deploy logs
you out. Changing it is also how you force-log-out every device.

### Moving your existing history up

The deployed app starts with an empty database. To carry over what you've already
logged locally:

```bash
fly sftp shell
# at the prompt:
put app/cogsec.db /data/cogsec.db
exit

fly apps restart          # reopen the DB cleanly
```

Going the other way — pull a backup down — is `get /data/cogsec.db ./backup.db` at
the same prompt. Worth doing occasionally; a single volume is not a backup.

### Day-to-day

| | |
|---|---|
| Deploy a change | `fly deploy` |
| Watch logs | `fly logs` |
| Check spend | `fly dashboard` → Billing |
| Change the passcode | `fly secrets set COGSEC_PASSCODE='…'` |

---

## Your data

- It's one file: `app/cogsec.db` locally, `/data/cogsec.db` on Fly. Back it up by
  copying it anywhere.
- Inspect it with any SQLite tool: `sqlite3 app/cogsec.db`.
- Delete individual entries with the ✕ button; delete everything by removing the
  file (a fresh, empty one is created on next start).

## Troubleshooting

- **"Address already in use" on start** — the app is already running in another
  Terminal window. Use that one, or stop it there first with `Ctrl-C`.
- **Links do nothing / "can't reach page"** — the server isn't running. Start it
  again with `./app/start` and keep the Terminal open.
- **`./app/start: permission denied`** — run `chmod +x app/start` once, then retry.
- **Deploy fails with "refusing to start an unauthenticated server"** — working as
  intended: `COGSEC_PASSCODE` isn't set. Run the `fly secrets set` line above.
- **Phone shows a stale page** — the service worker serves cached pages when the
  network fails. Pull down to refresh; if it sticks, tap **Lock** (which clears the
  cache) and log back in.
- **First load of the day is slow** — the machine was stopped and is waking up. A
  second or two, once.
- **Changed the CSS but the phone shows the old one** — bump `VERSION` in
  `app/static/sw.js`; that's what retires the old asset cache.

## Stack

Flask + SQLite + inline-SVG charts, served by gunicorn in production. No build step,
no JS framework, no external services. Manual equivalent of the launcher:
`.venv/bin/python app/server.py`.

**Auth** is a single passcode in `$COGSEC_PASSCODE`, compared with
`hmac.compare_digest` and throttled after 8 bad attempts. Leave it unset and there's
no gate at all — fine on `127.0.0.1`, which is why `fly.toml` sets
`COGSEC_REQUIRE_AUTH=1` to make an unauthenticated deploy impossible. Session cookies
are `HttpOnly` + `Secure` + `SameSite=Lax`; the SameSite setting is also what stands
in for CSRF tokens on these forms.
