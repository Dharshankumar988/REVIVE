import asyncio
import json
import os
import re
from typing import Any
from urllib import error, request

from dotenv import load_dotenv

try:
    from supabase import Client, create_client
except Exception:  # pragma: no cover - optional runtime dependency
    Client = Any  # type: ignore[misc,assignment]
    create_client = None  # type: ignore[assignment]

load_dotenv()

DEFAULT_INSTANT_ACTION = "Critical vitals detected. Start emergency assessment and monitor airway, breathing, and circulation."
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
_SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
_SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
_SUPABASE_CLIENT: Client | None = None
QUICK_REQUEST_HINTS = (
    "quick",
    "quich",
    "steps",
    "checklist",
    "handoff",
    "60-second",
    "60 second",
    "brief",
)

CONVERSATIONAL_HINTS = (
    "who are you",
    "who r u",
    "who are u",
    "what are you",
    "your name",
    "hi",
    "hello",
    "hey",
    "help",
    "thanks",
    "thank you",
)

CLINICAL_HINTS = (
    "hr",
    "spo2",
    "oxygen",
    "airway",
    "breathing",
    "circulation",
    "critical",
    "warning",
    "vitals",
    "triage",
    "hypoxia",
    "cardiac",
    "tachy",
    "handoff",
    "protocol",
    "patient",
)

# Local fallback corpus ensures guidance generation remains retrieval-backed even
# when cloud RAG tables are empty or unavailable.
LOCAL_RAG_CORPUS = [
    {
        "title": "Hypoxia Emergency",
        "text": "Prioritize airway, start oxygen support, monitor saturation continuously, and escalate immediately if SpO2 remains below 90 percent.",
    },
    {
        "title": "Cardiac Arrest Response",
        "text": "Confirm unresponsiveness and pulse absence, begin high-quality CPR, activate code response, and continue ACLS protocol.",
    },
    {
        "title": "Tachycardia Stabilization",
        "text": "Assess hemodynamic stability, monitor rhythm and pulse trend, maintain oxygenation, and prepare urgent escalation if instability persists.",
    },
    {
        "title": "Golden Hour Recheck",
        "text": "Reassess airway, breathing, circulation, and mental status every two minutes during high-risk observation windows.",
    },
    {
        "title": "Low Movement Monitoring",
        "text": "When movement drops with other abnormal vitals, assess responsiveness and signs of perfusion compromise immediately.",
    },
]


async def generate_instant_action(vitals: dict[str, Any]) -> str:
    """Return a one-sentence emergency instruction for critical states.

    Uses Groq when configured, and falls back to a safe default message on failures.
    """
    status = str(vitals.get("status", ""))
    if status != "Critical":
        return ""

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return _default_action_from_vitals(vitals)

    try:
        return await asyncio.wait_for(asyncio.to_thread(_generate_via_groq_sync, api_key, vitals), timeout=1.2)
    except Exception:
        return _default_action_from_vitals(vitals)


async def generate_chat_reply(message: str, context: dict[str, Any] | None = None) -> str:
    """Return a conversational assistant reply, preferring Gemini and optionally summarizing with Groq."""
    normalized_context = context or {}
    cleaned = message.strip()
    if not cleaned:
        return "Share a question or vitals. I will answer in quick clinical lines."

    quick_mode = _is_quick_request(cleaned)
    conversational_mode = _is_conversational_request(cleaned)
    clinical_mode = quick_mode or _is_clinical_request(cleaned)

    if not GEMINI_API_KEY:
        if quick_mode:
            return _fallback_quick_reply(normalized_context)
        if not clinical_mode or conversational_mode:
            return _fallback_conversational_reply(cleaned)
        return _fallback_chat_reply(cleaned, normalized_context)

    try:
        if quick_mode:
            gemini_reply = await asyncio.wait_for(
                asyncio.to_thread(_generate_quick_chat_reply_via_gemini_sync, cleaned, normalized_context),
                timeout=4.0,
            )
        elif not clinical_mode or conversational_mode:
            gemini_reply = await asyncio.wait_for(
                asyncio.to_thread(_generate_conversational_chat_reply_via_gemini_sync, cleaned),
                timeout=4.0,
            )
        else:
            gemini_reply = await asyncio.wait_for(
                asyncio.to_thread(_generate_chat_reply_via_gemini_sync, cleaned, normalized_context),
                timeout=4.0,
            )
    except Exception:
        if quick_mode:
            return _fallback_quick_reply(normalized_context)
        if not clinical_mode or conversational_mode:
            return _fallback_conversational_reply(cleaned)
        return _fallback_chat_reply(cleaned, normalized_context)

    groq_summary = _maybe_summarize_with_groq(gemini_reply, cleaned, normalized_context)
    return groq_summary or gemini_reply


async def generate_veteran_brief(vitals: dict[str, Any]) -> str:
    status = str(vitals.get("status", "Normal"))
    if status != "Critical":
        return ""

    query = (
        f"status={vitals.get('status')} hr={vitals.get('hr')} "
        f"spo2={vitals.get('spo2')} movement={vitals.get('movement')} escalation brief"
    )
    rag_chunks = _retrieve_rag_context(query=query, top_k=3)

    if not GEMINI_API_KEY:
        return _fallback_veteran_brief(vitals, rag_chunks)

    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_generate_veteran_brief_via_gemini_sync, vitals, rag_chunks),
            timeout=4.0,
        )
    except Exception:
        return _fallback_veteran_brief(vitals, rag_chunks)


def _generate_via_groq_sync(api_key: str, vitals: dict[str, Any]) -> str:
    from groq import Groq

    client = Groq(api_key=api_key)

    hr = vitals.get("hr")
    spo2 = vitals.get("spo2")
    movement = vitals.get("movement")

    prompt = (
        "You are an emergency triage assistant. Return exactly one short sentence. "
        "No bullets, no numbering, no extra explanation. "
        f"Vitals: HR={hr}, SpO2={spo2}, Movement={movement}, Status=Critical."
    )

    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": (
                    "Provide immediate, practical, medically conservative actions for first response. "
                    "Keep output under 20 words and exactly one sentence."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        max_tokens=40,
        temperature=0.1,
    )

    content = completion.choices[0].message.content if completion.choices else ""
    clean = (content or "").strip()
    return clean if clean else _default_action_from_vitals(vitals)


def _generate_chat_reply_via_gemini_sync(message: str, context: dict[str, Any]) -> str:
    vitals_summary = _format_vitals_context(context)
    prompt_parts = [
        "You are the REVIVE assistant.",
        "Reply in a natural, human tone.",
        "Keep the answer ultra concise: 1 to 2 short sentences, max 35 words.",
        "Use protocol-grounded support language with explicit escalation cues.",
        "Do not diagnose or claim definitive treatment authority.",
        f"User message: {message.strip()}",
    ]
    if vitals_summary:
        prompt_parts.append(f"Current dashboard context: {vitals_summary}")

    prompt = "\n".join(prompt_parts)
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.5, "maxOutputTokens": 220},
    }
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            "gemini-1.5-flash:generateContent?key="
            + GEMINI_API_KEY
        ),
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=4.0) as response:
            data = json.loads(response.read().decode("utf-8"))
    except error.URLError as exc:
        raise RuntimeError("gemini chat request failed") from exc

    text = _extract_gemini_text(data)
    if text:
        return text

    return _fallback_chat_reply(message, context)


def _generate_conversational_chat_reply_via_gemini_sync(message: str) -> str:
    prompt = "\n".join(
        [
            "You are the REVIVE assistant.",
            "The user asked a general non-clinical message (identity/help/small talk).",
            "Reply in a warm, human tone.",
            "Keep the answer concise: 1 to 2 short sentences, max 30 words.",
            "Do not inject vitals or clinical advice unless the user explicitly asks for it.",
            f"User message: {message.strip()}",
        ]
    )

    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.5, "maxOutputTokens": 120},
    }
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            "gemini-1.5-flash:generateContent?key="
            + GEMINI_API_KEY
        ),
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=4.0) as response:
            data = json.loads(response.read().decode("utf-8"))
    except error.URLError as exc:
        raise RuntimeError("gemini conversational request failed") from exc

    text = _extract_gemini_text(data)
    if text:
        return text

    return _fallback_conversational_reply(message)


def _generate_quick_chat_reply_via_gemini_sync(message: str, context: dict[str, Any]) -> str:
    vitals_summary = _format_vitals_context(context)
    prompt = "\n".join(
        [
            "You are REVIVE emergency copilot.",
            "Use concise senior emergency-clinician communication style.",
            "Do not diagnose. Give protocol-grounded support and explicit escalation cues.",
            "Return exactly five lines in this exact format:",
            "Risk: ...",
            "Action 1: ...",
            "Action 2: ...",
            "Action 3: ...",
            "Handoff: ...",
            "Each line must be short and practical.",
            f"User message: {message}",
            f"Dashboard context: {vitals_summary if vitals_summary else 'N/A'}",
        ]
    )

    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 180},
    }
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            "gemini-1.5-flash:generateContent?key="
            + GEMINI_API_KEY
        ),
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=4.0) as response:
            data = json.loads(response.read().decode("utf-8"))
    except error.URLError as exc:
        raise RuntimeError("gemini quick chat request failed") from exc

    text = _extract_gemini_text(data).strip()
    return text if text else _fallback_quick_reply(context)


def _generate_veteran_brief_via_gemini_sync(vitals: dict[str, Any], rag_chunks: list[str]) -> str:
    prompt_parts = [
        "You are a veteran emergency clinician support assistant.",
        "Do not diagnose. Provide protocol-grounded emergency support.",
        "Return exactly three lines with these labels:",
        "Senior Clinical Read: ...",
        "Next 60 Seconds: ...",
        "Handoff Script: ...",
        "Keep each line concise and operational.",
        "Always include likely support techniques and common emergency drug classes if clinically appropriate, without dosing.",
        f"Vitals: HR={vitals.get('hr')}, SpO2={vitals.get('spo2')}, Movement={vitals.get('movement')}, Status={vitals.get('status')}",
    ]
    if rag_chunks:
        prompt_parts.append("Retrieved protocol context:")
        prompt_parts.extend(f"- {chunk}" for chunk in rag_chunks[:3])

    payload = {
        "contents": [{"role": "user", "parts": [{"text": "\n".join(prompt_parts)}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 220},
    }

    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            "gemini-1.5-flash:generateContent?key="
            + GEMINI_API_KEY
        ),
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with request.urlopen(req, timeout=4.0) as response:
        data = json.loads(response.read().decode("utf-8"))

    text = _extract_gemini_text(data).strip()
    return text if text else _fallback_veteran_brief(vitals, rag_chunks)


def generate_detailed_steps(vitals: dict[str, Any]) -> list[str]:
    """Return three concise response steps, using Gemini as the source and Groq as an optional summarizer."""
    status = str(vitals.get("status", ""))
    hr = int(vitals.get("hr", 0) or 0)
    spo2 = int(vitals.get("spo2", 0) or 0)
    movement = int(vitals.get("movement", 0) or 0)

    query = f"status={status} hr={hr} spo2={spo2} movement={movement} emergency protocol"
    rag_chunks = _retrieve_rag_context(query=query, top_k=3)

    if status == "Critical" and spo2 < 90:
        base_steps = [
            "Check airway patency and start oxygen support immediately.",
            "Track SpO2 and respiratory effort continuously for the next several minutes.",
            "Escalate to emergency response if oxygen saturation does not improve quickly.",
        ]
    elif status == "Critical" and hr < 50:
        base_steps = [
            "Assess responsiveness and confirm pulse immediately.",
            "Prepare CPR workflow and emergency escalation equipment.",
            "Continue close pulse and breathing checks without interruption.",
        ]
    elif status == "Critical" and hr > 130:
        base_steps = [
            "Assess for chest pain, breathlessness, and perfusion instability.",
            "Maintain oxygenation and continuous rhythm observation.",
            "Escalate urgently if heart rate remains unstable or symptoms worsen.",
        ]
    elif status == "Warning" or hr < 60 or spo2 < 94:
        base_steps = [
            "Reposition patient and reassess airway and breathing mechanics.",
            "Trend heart rate and SpO2 each minute for early deterioration.",
            "Prepare escalation path if readings continue to decline.",
        ]
    else:
        base_steps = [
            "Continue standard monitoring and maintain airway checks.",
            "Track HR and SpO2 trend at regular intervals.",
            "Keep emergency kit ready and reassess if symptoms change.",
        ]

    try:
        if not GEMINI_API_KEY:
            return _blend_retrieved_steps(base_steps, rag_chunks)

        gemini_steps = _generate_detailed_steps_via_gemini_sync(vitals, base_steps, rag_chunks)
        groq_steps = _maybe_summarize_steps_with_groq(gemini_steps, vitals)
        return groq_steps or gemini_steps
    except Exception:
        return _blend_retrieved_steps(base_steps, rag_chunks)


def _generate_detailed_steps_via_gemini_sync(
    vitals: dict[str, Any],
    base_steps: list[str],
    rag_chunks: list[str],
) -> list[str]:
    prompt_parts = [
        "You are a conservative clinical decision support assistant.",
        "Return exactly three short steps, one per line, with no numbering or bullets.",
        "Use the supplied protocol context to refine the advice, but keep the result concise and actionable.",
        f"Vitals: HR={vitals.get('hr')}, SpO2={vitals.get('spo2')}, Movement={vitals.get('movement')}, Status={vitals.get('status')}",
        "Seed guidance:",
        *[f"- {step}" for step in base_steps],
    ]
    if rag_chunks:
        prompt_parts.append("Retrieved context:")
        prompt_parts.extend(f"- {chunk}" for chunk in rag_chunks[:3])

    prompt = "\n".join(prompt_parts)
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-1.5-flash:generateContent?key="
        + GEMINI_API_KEY
    )
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "maxOutputTokens": 200},
    }
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")

    try:
        with request.urlopen(req, timeout=3.0) as response:
            data = json.loads(response.read().decode("utf-8"))
    except error.URLError as exc:
        raise RuntimeError("gemini request failed") from exc

    text = _extract_gemini_text(data)
    parsed_steps = _parse_step_text(text)
    if len(parsed_steps) >= 3:
        return parsed_steps[:3]

    return _blend_retrieved_steps(base_steps, rag_chunks)


def _maybe_summarize_with_groq(gemini_reply: str, message: str, context: dict[str, Any]) -> str:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return ""

    try:
        return _summarize_gemini_reply_with_groq_sync(api_key, gemini_reply, message, context)
    except Exception:
        return ""


def _summarize_gemini_reply_with_groq_sync(
    api_key: str,
    gemini_reply: str,
    message: str,
    context: dict[str, Any],
) -> str:
    from groq import Groq

    client = Groq(api_key=api_key)
    vitals_summary = _format_vitals_context(context)
    prompt = (
        "Summarize the assistant answer into a concise, friendly reply that keeps the same meaning. "
        "If the answer is already concise, preserve it and only smooth the wording. "
        "Do not add new facts. Return 1-2 short sentences, max 30 words.\n"
        f"User message: {message.strip()}\n"
        f"Assistant draft: {gemini_reply.strip()}"
    )
    if vitals_summary:
        prompt += f"\nDashboard context: {vitals_summary}"

    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": (
                    "You refine Gemini-written REVIVE responses. Keep the tone human and concise. "
                    "Do not make the reply sound robotic."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        max_tokens=140,
        temperature=0.2,
    )

    content = completion.choices[0].message.content if completion.choices else ""
    clean = (content or "").strip()
    return clean if clean else gemini_reply


def _maybe_summarize_steps_with_groq(steps: list[str], vitals: dict[str, Any]) -> list[str]:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return []

    try:
        return _summarize_steps_with_groq_sync(api_key, steps, vitals)
    except Exception:
        return []


def _summarize_steps_with_groq_sync(api_key: str, steps: list[str], vitals: dict[str, Any]) -> list[str]:
    from groq import Groq

    client = Groq(api_key=api_key)
    prompt = (
        "Rewrite these clinical guidance steps as three concise, practical bullets without adding new facts. "
        "Keep the meaning aligned with the source guidance and make the wording clean and summary-like.\n"
        f"Vitals: HR={vitals.get('hr')}, SpO2={vitals.get('spo2')}, Movement={vitals.get('movement')}, Status={vitals.get('status')}\n"
        "Steps:\n" + "\n".join(f"- {step}" for step in steps[:3])
    )

    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": "Condense the provided steps into three short lines, one per line, and keep them grounded in the source.",
            },
            {"role": "user", "content": prompt},
        ],
        max_tokens=120,
        temperature=0.15,
    )

    content = completion.choices[0].message.content if completion.choices else ""
    parsed = _parse_step_text((content or "").strip())
    return parsed[:3] if len(parsed) >= 3 else []


def _default_action_from_vitals(vitals: dict[str, Any]) -> str:
    spo2 = int(vitals.get("spo2", 0) or 0)
    hr = int(vitals.get("hr", 0) or 0)

    if spo2 < 90:
        return "Critical SpO2 detected. Sit patient upright and monitor breathing closely."
    if hr < 50:
        return "Critical heart rate detected. Check pulse immediately and prepare emergency response."

    return DEFAULT_INSTANT_ACTION


def _is_quick_request(message: str) -> bool:
    lowered = message.lower()
    return any(token in lowered for token in QUICK_REQUEST_HINTS)


def _is_conversational_request(message: str) -> bool:
    lowered = message.lower().strip()
    if len(lowered) <= 24 and lowered in {"hi", "hello", "hey", "who are u", "who r u"}:
        return True
    return any(token in lowered for token in CONVERSATIONAL_HINTS)


def _is_clinical_request(message: str) -> bool:
    lowered = message.lower()
    return any(token in lowered for token in CLINICAL_HINTS)


def _fallback_quick_reply(context: dict[str, Any]) -> str:
    hr = _to_int(context.get("hr"))
    spo2 = _to_int(context.get("spo2"))
    movement = _to_int(context.get("movement"))
    status = str(context.get("status", "Normal"))
    trend = str(context.get("trend", "stable"))

    risk = "high acuity" if status == "Critical" or trend == "critical" or (spo2 is not None and spo2 < 90) else "elevated risk"
    return (
        f"Risk: {risk}.\n"
        "Action 1: Secure airway, start oxygen now.\n"
        "Action 2: Recheck HR and SpO2 every 60 seconds.\n"
        "Action 3: Escalate immediately if SpO2 stays below 90.\n"
        f"Handoff: HR {hr if hr is not None else 'NA'}, SpO2 {spo2 if spo2 is not None else 'NA'}, Movement {movement if movement is not None else 'NA'}, status {status}, trend {trend}."
    )


def _fallback_conversational_reply(message: str) -> str:
    lowered = message.lower().strip()
    if any(token in lowered for token in ("who are you", "who are u", "who r u", "what are you", "your name")):
        return "I am REVIVE Assistant. I can help with vitals trends, quick next-step guidance, and clean handoff summaries for your simulation."
    if any(token in lowered for token in ("help", "what can you do", "capabilities")):
        return "I can explain current vitals risk, suggest immediate priorities, and draft short handoff lines. Ask me anything from general help to critical-step support."
    if any(token in lowered for token in ("hi", "hello", "hey")):
        return "Hi, I am REVIVE Assistant. Tell me what you want to check and I will keep the response short and useful."
    if any(token in lowered for token in ("thanks", "thank you")):
        return "You are welcome. I am here whenever you need a quick summary or next-step support."
    return "I am here to help. Ask me about the dashboard, vitals interpretation, or immediate next-step guidance."


def _fallback_veteran_brief(vitals: dict[str, Any], rag_chunks: list[str]) -> str:
    hr = vitals.get("hr")
    spo2 = vitals.get("spo2")
    movement = vitals.get("movement")
    context_line = _sentence_from_chunk(rag_chunks[0]) if rag_chunks else "Prioritize airway and oxygen escalation."
    return (
        f"Senior Clinical Read: Critical hypoxemia-risk profile with HR {hr}, SpO2 {spo2}, movement {movement}. {context_line}\n"
        "Next 60 Seconds: Confirm airway patency, escalate oxygen delivery, repeat vitals immediately, and consider suction, bag-valve-mask support, airway adjuncts, bronchodilators, fluids, vasopressors, or IV access if clinically indicated.\n"
        f"Handoff Script: Adult patient unstable, HR {hr}, SpO2 {spo2}, movement {movement}, critical trend; airway and oxygen escalation initiated, urgent senior review requested, and advanced respiratory or hemodynamic support may be needed."
    )


def _fallback_chat_reply(message: str, context: dict[str, Any] | None) -> str:
    trimmed = message.strip()
    if not trimmed:
        return "Ask me anything about the dashboard, workflow, or current vitals."

    if context:
        hr = _to_int(context.get("hr"))
        spo2 = _to_int(context.get("spo2"))
        movement = _to_int(context.get("movement"))
        status = str(context.get("status", "Normal"))
        trend = str(context.get("trend", "stable"))
        scenario = str(context.get("scenario", "Unknown"))

        risk_bits: list[str] = []
        if spo2 is not None and spo2 < 90:
            risk_bits.append("severe hypoxemia")
        elif spo2 is not None and spo2 < 94:
            risk_bits.append("borderline oxygen reserve")

        if hr is not None and (hr < 50 or hr > 130):
            risk_bits.append("critical heart-rate deviation")
        elif hr is not None and (hr < 60 or hr > 110):
            risk_bits.append("heart-rate instability")

        if movement is not None and movement <= 2:
            risk_bits.append("very low movement responsiveness")

        if status == "Critical" or trend == "critical":
            urgency = "high-acuity"
        elif status == "Warning" or trend == "declining":
            urgency = "elevated-risk"
        else:
            urgency = "low-acuity"

        concern = ", ".join(risk_bits) if risk_bits else "no dominant red-flag marker"
        return (
            f"Clinical read: this is a {urgency} pattern in the {scenario} context with {concern}. "
            f"Priority actions: maintain airway-breathing-circulation checks, repeat vitals at short intervals, and escalate immediately if HR/SpO2 trend worsens. "
            f"Current snapshot: HR={hr if hr is not None else 'NA'}, SpO2={spo2 if spo2 is not None else 'NA'}, Movement={movement if movement is not None else 'NA'}, Status={status}, Trend={trend}."
        )

    return (
        "I can give a clinically structured summary if you share the latest HR, SpO2, movement, status, and trend. "
        "I will then provide risk level, immediate priorities, and escalation cues in a healthcare-style format."
    )


def _to_int(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except Exception:
        return None


def _format_vitals_context(context: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("hr", "spo2", "movement", "status", "trend", "scenario"):
        value = context.get(key)
        if value is None:
            continue
        parts.append(f"{key.upper()}={value}")
    return ", ".join(parts)


def _blend_retrieved_steps(base_steps: list[str], rag_chunks: list[str]) -> list[str]:
    steps = base_steps[:3]
    if rag_chunks:
        retrieved_line = _sentence_from_chunk(rag_chunks[0])
        if retrieved_line:
            steps[1] = retrieved_line
    return steps


def _extract_gemini_text(data: dict[str, Any]) -> str:
    candidates = data.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return ""

    content = candidates[0].get("content") if isinstance(candidates[0], dict) else None
    parts = content.get("parts") if isinstance(content, dict) else None
    if not isinstance(parts, list):
        return ""

    texts = [part.get("text", "") for part in parts if isinstance(part, dict) and isinstance(part.get("text"), str)]
    return "\n".join(texts).strip()


def _parse_step_text(text: str) -> list[str]:
    lines = [line.strip(" -\t") for line in text.splitlines()]
    steps = [line for line in lines if line]
    return steps


def _get_supabase_client() -> Client | None:
    global _SUPABASE_CLIENT

    if _SUPABASE_CLIENT is not None:
        return _SUPABASE_CLIENT

    if create_client is None:
        return None

    if not _SUPABASE_URL or not _SUPABASE_SERVICE_ROLE_KEY:
        return None

    try:
        _SUPABASE_CLIENT = create_client(_SUPABASE_URL, _SUPABASE_SERVICE_ROLE_KEY)
    except Exception:
        return None

    return _SUPABASE_CLIENT


def _retrieve_rag_context(query: str, top_k: int = 3) -> list[str]:
    remote_chunks = _retrieve_remote_chunks(query=query, top_k=top_k)
    if remote_chunks:
        return remote_chunks

    return _retrieve_local_chunks(query=query, top_k=top_k)


def _retrieve_remote_chunks(query: str, top_k: int) -> list[str]:
    client = _get_supabase_client()
    if client is None:
        return []

    try:
        response = (
            client.rpc(
                "search_rag_chunks_text",
                {
                    "query_text": query,
                    "match_count": top_k,
                },
            )
            .execute()
        )
    except Exception:
        return []

    rows = response.data or []
    chunks: list[str] = []
    for row in rows:
        text = row.get("chunk_text") if isinstance(row, dict) else None
        if isinstance(text, str) and text.strip():
            chunks.append(text.strip())
    return chunks


def _retrieve_local_chunks(query: str, top_k: int) -> list[str]:
    query_tokens = set(_tokenize(query))
    scored: list[tuple[int, str]] = []

    for doc in LOCAL_RAG_CORPUS:
        text = doc["text"]
        text_tokens = set(_tokenize(text))
        score = len(query_tokens.intersection(text_tokens))
        scored.append((score, text))

    scored.sort(key=lambda item: item[0], reverse=True)
    selected = [text for score, text in scored if score > 0][:top_k]

    if selected:
        return selected

    return [doc["text"] for doc in LOCAL_RAG_CORPUS[:top_k]]


def _sentence_from_chunk(chunk: str) -> str:
    sentences = [s.strip() for s in re.split(r"[.!?]", chunk) if s.strip()]
    if not sentences:
        return ""
    sentence = sentences[0]
    if not sentence.endswith("."):
        sentence += "."
    return sentence


def _tokenize(text: str) -> list[str]:
    return [token for token in re.findall(r"[a-zA-Z0-9]+", text.lower()) if len(token) >= 3]
