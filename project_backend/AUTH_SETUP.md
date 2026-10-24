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

For PostgreSQL, set `DATABASE_URL` to a `postgresql://` or `postgresql+psycopg://` URL. The backend normalizes the former to the psycopg driver. Back up the configured database and the existing dataset/model artifact folders together; the latter remain file-backed for compatibility with current training and download behavior.

In production, serve both origins over HTTPS, use a unique long `JWT_SECRET`, restrict `FRONTEND_URL` to the deployed UI, and register only the deployed OAuth callback URLs. Authenticated data APIs use bearer JWTs; the browser keeps them in tab-scoped session storage so refreshes work and signing out clears the local workspace state.
