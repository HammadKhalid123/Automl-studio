# AutoML Studio

A web app for exploring tabular datasets, preparing features, training and comparing machine learning models, and trying predictions in the browser.

> **Project status:** Portfolio/demo project. Training speed and saved-file persistence depend on the hosting plan you choose.

## Features

- Upload and profile CSV datasets, with charts and column summaries.
- Choose a classification or regression task and target column.
- Configure preprocessing, including missing-value handling, scaling, outlier handling, and duplicate removal.
- Select compatible scikit-learn models or run all compatible models.
- Compare cross-validation scores, evaluation metrics, parameters, and training time.
- Review evaluation charts, view run history, download trained models, and submit prediction data.
- Create an account, verify email, sign in, reset passwords, and optionally use GitHub or Google OAuth.
- Ask the built-in assistant questions about the dataset and training workflow.

## Tech stack

- **Frontend:** React 19, Vite 7
- **Backend:** Python, FastAPI, Uvicorn
- **ML/data:** scikit-learn, pandas, NumPy, joblib
- **Database:** SQLAlchemy; SQLite by default, PostgreSQL supported
- **Authentication:** JWT, email verification, optional GitHub/Google OAuth

## Run locally

Requirements: Python 3.10+ and Node.js/npm.

### 1. Start the API

In PowerShell:

```powershell
cd project_backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Open `project_backend/.env` and set a unique `JWT_SECRET` with at least 32 characters. Then start the API:

```powershell
python -m uvicorn app.main:app --reload --port 8000
```

The API docs are available at <http://127.0.0.1:8000/docs> and the health check at <http://127.0.0.1:8000/health>.

### 2. Start the frontend

In a second PowerShell window:

```powershell
cd frontend
npm install
npm run dev
```

Open the local URL printed by Vite (usually <http://localhost:5173>). During local development, Vite proxies API requests to the backend on port 8000.

## Configuration

Backend settings are read from `project_backend/.env`. Use `.env.example` as the template. Never commit `.env` or put credentials in frontend variables.

| Variable | Purpose |
| --- | --- |
| `JWT_SECRET` | Required signing secret; use a unique value of at least 32 characters. |
| `DATABASE_URL` | Optional SQLAlchemy URL. If empty, the app uses local SQLite. PostgreSQL is supported. |
| `FRONTEND_URL` | Frontend origin allowed for the deployed app and used after authentication flows. |
| `BACKEND_URL` | Public backend origin; used for OAuth callback URLs. |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `MAIL_FROM` | Optional SMTP configuration for verification and password-reset emails. SMTP uses STARTTLS. |
| `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` | Optional GitHub OAuth credentials. |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | Optional Google OAuth credentials. |
| `GROQ_API_KEY` | Optional key for the assistant's hosted LLM integration. |

Email verification and password reset require working email delivery settings. OAuth providers also need their callback URLs registered with the provider:

```text
${BACKEND_URL}/auth/github/callback
${BACKEND_URL}/auth/google/callback
```

For deployment, configure `VITE_API_URL` in the frontend build environment to point to the public API origin. Set the backend's `FRONTEND_URL` and `BACKEND_URL` to the deployed HTTPS URLs.

## Data and deployment notes

- By default, account data is stored in SQLite under `project_backend/data/`.
- Uploaded datasets, job history, and trained model artifacts use local app storage. A host with ephemeral storage can lose these files after a restart or redeploy; use persistent storage or external storage for data you need to keep, and back it up.
- Model training uses CPU and memory. Small demos may work on constrained free instances, while larger datasets or running many models can be slow or exceed the host's memory limit.
- Free hosting plans can sleep, impose resource limits, or change their terms. Verify the provider's current limits before relying on a deployment.
- Do not commit `.env`, API keys, OAuth secrets, SMTP passwords, uploaded datasets, databases, or trained model files.

## Repository layout

```text
frontend/                  React + Vite application
project_backend/
  app/api/                 API routes (datasets, jobs, models, auth, assistant)
  app/core/                Configuration, authentication, and storage helpers
  app/db/                  SQLAlchemy models and database setup
  app/services/            Profiling, preprocessing, training, evaluation, email
  requirements.txt         Python dependencies
```

## License

No license has been added yet. All rights are reserved unless a license is added to this repository.
