# 🚑 REVIVE: Golden Hour & Triage Monitor

**REVIVE** is a real-time patient vitals monitoring system built for high-acuity real-world environments. It is specifically designed to support the "Golden Hour" protocol—the critical window following traumatic injury or sudden illness where rapid medical intervention has the highest chance of preventing death.

The platform bridges the gap between raw biometric telemetry and actionable clinical triage, making it invaluable for general health monitoring, rapid response teams, and mobile emergency units.

---

## 🌟 Real-World Applications

- **Golden Hour Protocol**: Rapid, automated telemetry analysis ensures that deteriorating vitals are flagged immediately, calculating risk trajectories instantly to support rapid escalation.
- **General Health Monitoring**: Continuous, passive monitoring of key indicators (Heart Rate, SpO2, Movement) for at-risk patients, establishing baseline data to identify long-term deterioration.
- **Rapid Triage Support**: AI-driven clinical context provides on-the-spot handoff scripts and escalation briefs, allowing veteran clinicians and first responders to make informed decisions under pressure.

---

## ⚡ Core Capabilities

- **Real-Time Vitals Streaming**: Low-latency WebSocket connections broadcast live patient telemetry continuously.
- **AI-Powered Emergency Guidance**: Grounded, non-diagnostic guidance powered by optimized Groq and Gemini models, offering immediate next-step actions based on localized medical protocols (RAG).
- **Intelligent Processing Engine**: Continuous risk detection (Critical / Warning / Normal) combined with anomaly detection against patient baselines.
- **Robust Role-Based Authentication**: Secure admin approval system designed for medical and administrative staff.
- **Simulation Engine**: Built-in scenarios (Stable, Gradual Decline, Cardiac Event, Arrest) for training and protocol testing without requiring active hardware.

---

## 🏗️ Architecture Stack

- **Frontend**: Next.js (Robust client application for command centers)
- **Backend**: FastAPI (High-performance API and WebSocket handler)
- **Database**: Supabase (PostgreSQL, Auth, and Vector Storage for RAG)
- **AI Engine**: Optimized dual-model approach using Gemini and Groq (with global caching for near-instant response times)

### 🔌 API Services
```http
GET  /healthz              # System status
POST /api/vitals           # Ingest telemetry
GET  /api/vitals/latest    # Fetch snapshot
POST /api/chat             # AI Copilot queries
POST /api/process          # Trigger RAG/AI processing
WS   /ws/vitals            # Live data broadcast
```

---

## 🤖 AI & Clinical RAG System

REVIVE utilizes a hybrid AI strategy optimized for speed and reliability in critical moments:
- **Zero-Latency Design**: API keys and clients (e.g., Groq) are cached globally, eliminating connection setup overhead during high-stakes queries.
- **Protocol Grounding**: Responses are strictly tied to localized RAG vectors or fallback clinical corpuses.
- **Action-Oriented Outputs**: Generates 60-second action plans and structured handoff scripts instead of conversational bloat.

---

## 🛡️ Disclaimer

*REVIVE is currently a prototype built to demonstrate AI-assisted telemetry and triage workflows. It is not a certified medical device and must not be used as the sole basis for clinical decision-making.*
