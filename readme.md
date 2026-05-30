# 🚑 REVIVE: Golden Hour & General Health Monitoring System

**REVIVE** is a highly responsive, real-time patient vitals monitoring platform designed specifically for high-acuity, real-world environments. Its primary goal is to empower medical professionals during the **"Golden Hour"**—the critical 60-minute window following traumatic injury or sudden illness where rapid medical intervention holds the highest probability of preventing death.

By bridging the gap between raw biometric telemetry and actionable clinical triage, REVIVE serves as an invaluable asset for intensive care units, rapid response teams, and mobile emergency responders.

---

## 🌟 Real-World Applications

### The Golden Hour Protocol
In emergency trauma scenarios, every second counts. REVIVE's underlying analytics engine continuously processes heart rate, SpO2, and patient movement, automatically calculating risk trajectories. When a patient's vitals rapidly change, the system dynamically shifts its threat assessment, flagging the event instantly to support immediate escalation and life-saving physical interventions.

### General Health Monitoring
Beyond acute emergencies, REVIVE acts as a passive, continuous monitoring system. It establishes patient baselines to track subtle, long-term physiological changes. This makes it highly effective for chronic care management, post-operative observation, and identifying early signs of declining health before they become critical.

### REVIVE Assistant (Powered by Pulse AI)
Integrated directly into the system is the **REVIVE Assistant**—a diagnostic copilot powered by the advanced Pulse AI backend (`https://huggingface.co/spaces/Dkb988/pulse-ai-backend`). The Assistant provides:
- Immediate medical image analysis and condition diagnostics for medical practitioners.
- On-the-spot clinical context and actionable triage protocols.
- **Intentional Lockout**: The assistant intentionally locks down during critical Golden Hour emergencies to ensure responders are entirely focused on physical life-support rather than interacting with an AI interface.

---

## ⚡ Core Capabilities

- **Real-Time Vitals Streaming**: Low-latency WebSocket connections broadcast live patient telemetry continuously, reflecting minute-by-minute changes in simulated or physical conditions.
- **Dynamic Scenario Engine**: The AI and threat level assessments respond dynamically. As parameters like HR and SpO2 fluctuate (e.g., Sudden Cardiac Event vs. Gradual Decline), the system recalibrates its guidance accordingly.
- **Intelligent Processing Engine**: Continuous risk detection (Critical / Warning / Normal) combined with anomaly tracking against established physiological baselines.
- **AI-Powered Diagnostics**: Grounded guidance powered by optimized Groq and Gemini models, offering immediate next-step actions based on localized medical protocols (RAG).

---

## 🏗️ Architecture Stack

- **Frontend**: Next.js (Robust, streamlined client application for command centers)
- **Backend Analytics**: FastAPI (High-performance API and WebSocket handler)
- **Diagnostic Assistant**: Pulse AI backend (Gradio/HuggingFace) for comprehensive multimodal medical analysis.
- **Database**: Supabase (PostgreSQL and Vector Storage for RAG)
- **AI Engine**: Optimized dual-model approach using Gemini and Groq (with global caching for near-instant response times). Both APIs work efficiently in tandem to process text and data rapidly.

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
- **Action-Oriented Outputs**: Generates structured handoff scripts and 60-second action plans instead of conversational bloat.

---

## 🛡️ Disclaimer

*REVIVE is currently a prototype built to demonstrate AI-assisted telemetry and triage workflows. It is not a certified medical device and must not be used as the sole basis for clinical decision-making.*
