Render Deployment Steps

1. Push this repository to GitHub (including render.yaml).
2. Go to https://dashboard.render.com and log in.
3. Click New +, then Blueprint.
4. Select your RSTRating repository.
5. Render will detect render.yaml automatically.
6. Confirm service creation for rstrating-accounts-api.
7. Wait for first deploy to complete.
8. Open the service URL and verify /health returns status ok.

Persistent Storage

The service uses a Render Starter plan with a 1 GB persistent disk mounted at /var/data.
DB_PATH is set to /var/data/accounts.db — the database survives restarts and redeploys.
If you change the disk mount path, update the DB_PATH env var in the Render dashboard to match.

Environment variables to verify

1. JWT_SECRET: generated automatically by render.yaml.
2. FRONTEND_ORIGINS: must include your frontend origin.
   For GitHub Pages use https://xeroxandarian.github.io
3. DB_PATH: /var/data/accounts.db

Connect frontend to backend

1. Open the public BrowserApp page.
2. In Backend API URL enter your Render URL, example:
   https://rstrating-accounts-api.onrender.com
3. Click Save API URL.
4. Register and log in.

Exporting data

Two export options are available from the admin account:

Option 1 — JSON backup (structured, importable)
  GET /backup/export   requires admin JWT
  Returns all users, leagues, memberships, and stats as a JSON document.
  Can be re-imported via POST /backup/import.

Option 2 — Raw database download
  GET /admin/download-db   requires admin JWT
  Downloads the live SQLite .db file as rstrating_backup_<timestamp>.db.
  Open locally with any SQLite browser (DB Browser for SQLite, DBeaver, etc).

Notes

1. Render Starter services do not sleep — no cold start delay.
2. Persistent disk data is retained across deploys and restarts.
3. If CORS errors appear, add the exact frontend origin in FRONTEND_ORIGINS.
4. To seed demo data after first deploy, run: python demo_seed.py --users 10 --leagues 4
