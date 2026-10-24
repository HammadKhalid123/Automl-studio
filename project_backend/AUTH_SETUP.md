# AutoML Studio authentication setup

## Local startup

1. From `project_backend`, install the pinned dependency ranges and run the API:

   ```powershell
   .\venv\Scripts\python.exe -m pip install -r requirements.txt
   .\venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
   ```

   The API creates the SQLAlchemy database tables at startup. SQLite is the default and stores account/authentication data in `project_backend/data/app.db`. The existing job/artifact history store in `project_backend/data/automl.sqlite3` and filesystem artifacts continue to be used by the workspace.

2. From `frontend`, start the UI with `npm run dev`. The Vite development proxy forwards API routes to `http://localhost:8000`.

3. `project_backend/.env` is loaded by the backend. `.env.example` lists the supported variables. `JWT_SECRET` must contain at least 32 characters; the local ignored `.env` now has a generated persistent key. Do not commit `.env` or reuse a development key in production.

## Email and OAuth

Configure `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, and `MAIL_FROM` to deliver verification and password-reset messages. SMTP uses STARTTLS. Sign-up sends a styled HTML email containing a six-digit, single-use verification code that expires after 10 minutes. Enter it on the verification screen; no frontend URL is embedded in the verification email, so mobile email apps do not try to open `localhost` on the phone.

For each OAuth application, register these backend callback URLs (replace the host and scheme in deployments):

- GitHub: `${BACKEND_URL}/auth/github/callback`
- Google: `${BACKEND_URL}/auth/google/callback`

Set the corresponding client ID and secret in the backend environment. `FRONTEND_URL` is the post-login/verification destination. OAuth returns to the frontend at `/oauth/callback`; this route stays separate from `/auth/*`, which the local Vite server proxies to FastAPI. For a deployed frontend, set `VITE_API_URL` at frontend build time to the API origin, and set `BACKEND_URL` to the publicly reachable API origin.

## Database deployment

For a hosted deployment, connect a persistent PostgreSQL database and set `DATABASE_URL` to its connection string. FastAPI Cloud's Neon integration injects `DATABASE_URL` when a Neon database is linked to the app. The same PostgreSQL database stores accounts, verification tokens, and run history/results. Without it, the app falls back to local SQLite; on hosts with an ephemeral filesystem, accounts and history disappear on restart or scale-to-zero. The API health response reports `persistent_database` and `persistent_history`, and startup logs a warning when SQLite is active.

Uploaded datasets and trained pipeline files still live on the app filesystem. They can disappear on restart even when account/history persistence is configured; use external object storage or a persistent volume before relying on those files long-term. Run history keeps its compact report in PostgreSQL, so prior evaluations remain visible after a restart, but model download/prediction may need the artifact to be retrained if that file is gone.

In production, serve both origins over HTTPS, use a unique long `JWT_SECRET`, restrict `FRONTEND_URL` to the deployed UI, and register only the deployed OAuth callback URLs. Authenticated data APIs use bearer JWTs; the browser keeps them in tab-scoped session storage so refreshes work and signing out clears the local workspace state.
