# 🚑 REVIVE — Real-time Evaluation of Vitals & Intelligent Virtual Emergency Support

<p align="center">
  <strong>AI-powered patient vitals monitoring for the moments that matter most.</strong>
</p>

---

## 🌟 Overview

**REVIVE** is a highly responsive, real-time patient vitals monitoring platform designed for high-acuity, real-world environments. Its primary goal is to empower medical professionals during the **"Golden Hour"** — the critical 60-minute window following traumatic injury or sudden illness where rapid medical intervention holds the highest probability of preventing death.

By bridging the gap between raw biometric telemetry and actionable clinical triage, REVIVE serves as an invaluable asset for intensive care units, rapid response teams, and mobile emergency responders.

---

## ⚡ Core Capabilities

| Capability | Description |
|---|---|
| **Real-Time Vitals Streaming** | Low-latency WebSocket connections broadcast live patient telemetry (HR, SpO₂, movement) continuously |
| **Dynamic Scenario Engine** | AI and threat assessments adapt as parameters fluctuate — from stable baselines to sudden cardiac events |
| **Intelligent Risk Detection** | Continuous risk classification (Critical / Warning / Normal) with anomaly tracking against baselines |
| **AI-Powered Diagnostics** | Grounded guidance via Groq + Gemini models with RAG — actionable next-step protocols in real time |
| **Golden Hour Protocol** | Automatic system-wide escalation during critical windows, including assistant lockout |

---

## 🤖 REVIVE Assistant (Powered by Pulse AI)

Integrated directly into the dashboard is the **REVIVE Assistant** — a diagnostic copilot powered by the **Pulse AI** backend and the `meta-llama/Llama-3.2-11B-Vision-Instruct` model via HuggingFace Inference API.

### Features
- 💬 **Natural language medical Q&A** — describe symptoms, ask about conditions, request triage protocols
- 🖼️ **Medical image analysis** — upload images for AI-powered visual diagnostics
- 🪟 **Glassmorphic floating widget** — premium glass-effect UI with drag-move and resize support
- 🔒 **Intentional lockout** — automatically disabled during Golden Hour emergencies to keep responders focused on life-support

### Design
The assistant widget uses a multi-layered glassmorphism design:
- Deep `backdrop-filter: blur(24px)` with saturation boost
- Gradient borders with refraction highlight simulation
- Noise texture overlay for realistic glass depth
- Smooth open/close animations and typing indicators
- Draggable header + resizable via corner handle

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (Next.js)                    │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐ │
│  │  Dashboard    │  │  Vitals      │  │   REVIVE      │ │
│  │  (page.tsx)   │  │  Charts      │  │   Assistant   │ │
│  └──────┬───────┘  └──────┬───────┘  └───────┬───────┘ │
│         │                 │                   │         │
│         ▼                 ▼                   ▼         │
│    WebSocket API     REST API        HuggingFace API    │
└─────────┬─────────────┬──────────────────┬──────────────┘
          │             │                  │
          ▼             ▼                  ▼
   ┌─────────────┐ ┌────────────┐  ┌──────────────────┐
   │  FastAPI     │ │ Supabase   │  │ HF Inference API │
   │  Backend     │ │ (Postgres  │  │ Llama-3.2-11B    │
   │  + WebSocket │ │ + Vectors) │  │ Vision-Instruct  │
   └─────────────┘ └────────────┘  └──────────────────┘
```

### Tech Stack
- **Frontend**: Next.js 15 + React 19 + Tailwind CSS + Recharts
- **Backend**: FastAPI (WebSocket + REST)
- **AI Models**: Groq + Gemini (vitals analysis) · Llama 3.2 Vision (assistant)
- **Database**: Supabase (PostgreSQL + pgvector for RAG)
- **Mobile**: Capacitor (Android)

---

## 🚀 Getting Started

### Prerequisites
- Node.js 18+
- Python 3.10+ (for backend)
- A HuggingFace API token ([get one here](https://huggingface.co/settings/tokens))

### 1. Clone the Repository
```bash
git clone https://github.com/Dharshankumar988/REVIVE.git
cd REVIVE
```

### 2. Frontend Setup
```bash
cd frontend
npm install
```

Create a `.env.local` file (or copy from `.env.example`):
```env
NEXT_PUBLIC_WS_URL=ws://localhost:8080/ws/vitals
NEXT_PUBLIC_SUPABASE_URL=<your-supabase-url>
NEXT_PUBLIC_SUPABASE_ANON_KEY=<your-supabase-anon-key>
NEXT_PUBLIC_HF_TOKEN=<your-huggingface-token>
```

Start the dev server:
```bash
npm run dev
```

### 3. Backend Setup
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8080
```

---

## 🔌 API Endpoints

```http
GET  /healthz              # System health check
POST /api/vitals           # Ingest telemetry data
GET  /api/vitals/latest    # Fetch latest vitals snapshot
POST /api/chat             # AI Copilot queries (RAG)
POST /api/process          # Trigger RAG/AI processing
WS   /ws/vitals            # Live vitals broadcast
```

---

## 🧠 AI & Clinical RAG System

REVIVE utilizes a hybrid AI strategy optimized for speed and reliability:

- **Zero-Latency Design** — API clients cached globally, eliminating connection overhead during critical queries
- **Protocol Grounding** — Responses tied to localized RAG vectors and clinical corpuses
- **Action-Oriented Outputs** — Generates structured handoff scripts and 60-second action plans
- **Vision Analysis** — Llama 3.2 Vision model processes medical images for diagnostic support

---

## 📱 Mobile Support

REVIVE supports Android deployment via **Capacitor**:

```bash
npm run mobile:android
```

This builds the Next.js app, syncs with Capacitor, and opens Android Studio.

---

## 🛡️ Disclaimer

> *REVIVE is a prototype built to demonstrate AI-assisted telemetry and triage workflows. It is **not** a certified medical device and must not be used as the sole basis for clinical decision-making.*
