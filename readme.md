# REVIVE

Production-ready full-stack setup with:
- `frontend/`: Next.js app deployed on Vercel.
- `backend/`: FastAPI stateless API deployed on Google Cloud Run.

## Architecture

The backend now follows an app-package layout:

```text
backend/
  app/
    api/routes.py              # HTTP + WebSocket routes
    core/config.py             # environment configuration
    schemas/requests.py        # request models (JSON payloads)
    services/
      monitoring.py            # vitals risk/trend logic
      processor.py             # vitals/chat processing pipeline
      runtime.py               # in-memory runtime state
      simulation.py            # auto simulator service
      ws.py                    # WebSocket connection manager
    main.py                    # FastAPI app factory
  Dockerfile                   # Cloud Run-ready container
  requirements.txt             # includes gunicorn + uvicorn worker
  .env.example                 # backend environment template

frontend/
  app/page.tsx                 # dashboard UI + API calls
  lib/api.ts                   # API/WS base URL resolution
  .env.example                 # frontend environment template
```

## Stateless API Behavior

All backend interactions are request/response based with structured JSON.
No CLI prompts are required for backend operations.

Key endpoints:
- `GET /healthz` health check.
- `POST /api/vitals` ingest vitals payload.
- `GET /api/vitals/latest` fetch latest processed vitals.
- `POST /api/chat` assistant response endpoint.
- `GET /api/simulation/scenario` fetch active simulation mode.
- `POST /api/simulation/scenario` update simulation mode by JSON.
- `POST /api/process` simple data processing endpoint (`average|sum|min|max`).
- `GET /` service status.
- `WS /ws/vitals` real-time stream.

## Local Development

### 1. Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

### 2. Frontend

```bash
cd frontend
npm install
copy .env.example .env.local
npm run dev
```

Ensure in `frontend/.env.local`:
- `NEXT_PUBLIC_API_URL=http://localhost:8080`
- `NEXT_PUBLIC_WS_URL=ws://localhost:8080/ws/vitals`

## Deployment Guide

### Deploy Frontend on Vercel (Step by Step)

1. Push your repository to GitHub.
2. Open Vercel and click `Add New -> Project`.
3. Import this repository.
4. Set `Root Directory` to `frontend`.
5. Framework preset should auto-detect as `Next.js`.
6. Configure environment variables in Vercel project settings:
   - `NEXT_PUBLIC_API_URL=https://<your-cloud-run-backend-url>`
   - `NEXT_PUBLIC_WS_URL=wss://<your-cloud-run-backend-host>/ws/vitals`
   - `NEXT_PUBLIC_SUPABASE_URL=<your-supabase-url>`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY=<your-supabase-anon-key>`
7. Click `Deploy`.
8. After deploy, test:
   - page loads,
   - dashboard can call `/api/vitals/latest` via backend URL,
   - chat endpoint returns responses.

### Deploy Backend on Google Cloud Run (Step by Step)

1. Install and authenticate Google Cloud CLI:
   - `gcloud auth login`
   - `gcloud config set project <PROJECT_ID>`
2. Enable required services:
   - `gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com`
3. From repo root, build backend container:
   - `gcloud builds submit --tag gcr.io/<PROJECT_ID>/revive-backend ./backend`
4. Deploy to Cloud Run:
   - `gcloud run deploy revive-backend --image gcr.io/<PROJECT_ID>/revive-backend --platform managed --region <REGION> --allow-unauthenticated --port 8080`
5. Set runtime environment variables on Cloud Run service:
   - `APP_ENV=production`
   - `LOG_LEVEL=INFO`
   - `CORS_ORIGINS=https://<your-vercel-domain>`
   - `GROQ_API_KEY=<key>`
   - `GEMINI_API_KEY=<key>`
   - `SUPABASE_URL=<url>`
   - `SUPABASE_SERVICE_ROLE_KEY=<key>`
6. Re-deploy after env vars update (or set via Cloud Run console and deploy revision).
7. Verify backend health:
   - `https://<cloud-run-url>/healthz`
8. Update Vercel env vars to the Cloud Run URL and redeploy frontend.

## Scaling Notes

- Cloud Run auto-scales by request volume.
- Gunicorn with Uvicorn workers is configured in Dockerfile for production serving.
- CORS is environment-driven via `CORS_ORIGINS`.
- Frontend uses environment-based API routing (`frontend/lib/api.ts`) and development-only localhost fallbacks.

## Safety Disclaimer

This project is a decision-support prototype for educational and demonstration use only. It is not a certified medical device.