Render Deployment Steps

1. Push this repository to GitHub (including render.yaml).
2. Go to https://dashboard.render.com and log in.
3. Click New +, then Blueprint.
4. Select your RSTRating repository.
5. Render will detect render.yaml automatically.
6. Confirm service creation for rstrating-accounts-api.
7. Wait for first deploy to complete.
8. Open the service URL and verify /health returns status ok.

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

Notes

1. Render free web services sleep when idle. First request after idle can take time.
2. The attached disk keeps accounts data between deploys and restarts.
3. If CORS errors appear, add exact frontend origin in FRONTEND_ORIGINS.
