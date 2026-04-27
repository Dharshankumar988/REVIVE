🚑 REVIVE

Real-time patient vitals monitoring dashboard with emergency-oriented
decision support.

------------------------------------------------------------------------

🌟 Overview

REVIVE is a full-stack monitoring system that simulates, processes, and
visualizes patient vitals in real time.

It is built as two deployable services:
- Frontend: Next.js (Dashboard UI)
- Backend: FastAPI (Deployed on Render)

Supports real-time streaming, AI guidance, and simulation-driven
testing.

------------------------------------------------------------------------

⚡ Key Features

-   Real-time vitals streaming via WebSockets
-   Live dashboard with charts & risk indicators
-   AI-powered emergency guidance (with fallback support)
-   Built-in simulation engine for realistic scenarios
-   Role-based access (admin approval system)
-   Cloud deployment ready (Render + Vercel)

------------------------------------------------------------------------

🏗️ Architecture

Frontend (Next.js) │ ├── Auth + Dashboard + Charts │ ▼ Backend (FastAPI
on Render) │ ├── REST APIs + WebSocket ├── Processing Pipeline (risk +
anomalies) ├── Simulation Engine │ ▼ Supabase (DB + Auth + RAG)

------------------------------------------------------------------------

🔌 Core API

GET /healthz
POST /api/vitals
GET /api/vitals/latest
POST /api/chat
POST /api/process
WS /ws/vitals

------------------------------------------------------------------------

🧠 Processing Engine

-   Risk Detection (Critical / Warning / Normal)
-   Trend Analysis (decline + spikes)
-   Anomaly Detection (baseline comparison)
-   Live broadcast via WebSocket

------------------------------------------------------------------------

🤖 AI + RAG System

-   Emergency guidance generation
-   Gemini / Groq with fallback
-   Supabase RAG or local fallback
-   Safe, non-diagnostic outputs

------------------------------------------------------------------------

🧪 Simulation System

-   Built-in auto simulator
-   Scenarios: Stable, Decline, Cardiac Event, Arrest
-   Real-time demo without devices

------------------------------------------------------------------------

🗄️ Data & Auth

-   Supabase for auth, storage, logs, RAG
-   Role-based access with admin approval

------------------------------------------------------------------------

🚀 Deployment

-   Backend: Render
-   Frontend: Vercel
-   Database: Supabase

------------------------------------------------------------------------

🔄 Data Flow

Simulator → Backend → Processing → AI → Database → WebSocket → Frontend

------------------------------------------------------------------------

💪 Strengths

-   Real-time + fallback architecture
-   Intelligent processing + AI
-   Strong demo capability
-   Practical auth system
-   Deployment-ready

------------------------------------------------------------------------

⚠️ Limitations

-   No automated tests
-   Simulator complexity
-   Some configs not fully wired

------------------------------------------------------------------------

🛡️ Disclaimer

Prototype only. Not a certified medical system.

------------------------------------------------------------------------

⭐ Final Note

Built for real-time monitoring demos with AI and simulation.
