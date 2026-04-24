# 🚑 REVIVE
**Real-time Evaluation of Vitals & Intelligent Virtual Emergency Support**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat&logo=fastapi)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-black?style=flat&logo=next.js)](https://nextjs.org/)
[![Groq](https://img.shields.io/badge/Inference-Groq-orange)](https://groq.com/)

REVIVE is an AI-assisted emergency response and decision support system designed to assist clinicians and responders during critical situations. By monitoring patient vital signs in real-time and utilizing a dual-layer AI architecture (Groq + Gemini), the system identifies life-threatening anomalies and provides immediate, actionable guidance during the **Golden Hour**.

---

## 🧠 Overview
In medical emergencies, the **"Golden Hour"** is the window where rapid intervention significantly improves survival chances. REVIVE bridges the gap between monitoring and action by transforming raw physiological data into structured emergency protocols.

## ⚙️ Working Principle
The system operates through a 4-stage pipeline:
1. **📡 Continuous Monitoring:** Tracks Heart Rate, Oxygen Saturation (SpO₂), and Movement via simulated streams.
2. **🚨 Real-Time Detection:** Rule-based thresholding identifies sudden spikes, drops, or cessation of movement.
3. **🔍 Historical Analysis:** Compares current data against baseline trends to detect gradual deterioration (e.g., progressive hypoxia).
4. **🚑 Action Guidance:** Provides dynamic, step-by-step instructions based on risk classification: **Normal, Warning, or Critical.**

## 🏗️ Tech Stack
* **Frontend:** Next.js 14, Tailwind CSS, shadcn/ui, Recharts.
* **Backend:** FastAPI (Python), PostgreSQL, SQLAlchemy.
* **Real-time:** WebSockets for low-latency vitals streaming.
* **AI Engine (Speed):** **Groq API** (Llama-3.3-70b) for sub-second "Instant Action" responses.
* **AI Engine (Depth):** **Google Gemini API** + **ChromaDB** (RAG) for detailed medical protocol retrieval.
* **Mobile Wrapper:** **Ionic Capacitor** for native Android/iOS deployment.

## 🤖 AI Architecture: "AI Assists, Humans Act"
REVIVE uses a unique hybrid AI strategy:
* **Groq Layer:** Triggers instantly upon anomaly detection to provide a 1-sentence life-saving instruction (e.g., "Check airway now").
* **Gemini Layer:** Performs **Retrieval-Augmented Generation (RAG)** to provide deep-dive explanations and a 2-minute "Golden Hour" support timer for repeated tasks like pulse checks.

---

## 🚀 Getting Started

### Prerequisites
* Python 3.10+
* Node.js 18+
* Google Gemini API Key
* Groq API Key

### Installation

1. **Clone the Repository:**
   ```bash
   git clone [https://github.com/your-username/revive-emergency-ai.git](https://github.com/your-username/revive-emergency-ai.git)
   cd revive-emergency-ai

   Backend Setup:

Bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env      # Add your API keys to this file
python main.py
Frontend Setup:

Bash
cd ../frontend
npm install
npm run dev
📱 Mobile Deployment
To generate the Android/iOS application using Capacitor:

Bash
npm run build
npx cap add android
npx cap copy
npx cap open android
🔐 Safety Disclaimer
This project is a decision-support prototype. It is intended for educational and demonstration purposes only. It is not a certified medical device. In a real emergency, always prioritize the instructions of qualified healthcare providers and local emergency services (e.g., 911, 999, 112).

📄 License
Distributed under the MIT License. See LICENSE for more information.