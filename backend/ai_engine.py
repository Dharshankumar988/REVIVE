import asyncio
import hashlib
import json
import os
import re
from typing import Any
from urllib import error, request
from urllib.parse import quote_plus, urljoin, urlsplit

from dotenv import load_dotenv

try:
    from supabase import Client, create_client  # type: ignore[import-not-found]
except Exception:  # pragma: no cover - optional runtime dependency
    Client = Any  # type: ignore[misc,assignment]
    create_client = None  # type: ignore[assignment]

load_dotenv()

DEFAULT_INSTANT_ACTION = "Critical vitals detected. Start emergency assessment and monitor airway, breathing, and circulation."
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash").strip() or "gemini-2.0-flash"
_SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
_SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
_SUPABASE_CLIENT: Any | None = None
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

SNAPSHOT_HINTS = (
    "current snapshot",
    "current vitals",
    "latest vitals",
    "latest snapshot",
    "vitals now",
    "vitals right now",
    "latest reading",
    "latest readings",
    "current reading",
    "current readings",
    "snapshot",
)

HEMORRHAGE_TOKENS = (
    "hemorrhage",
    "haemorrhage",
    "hemorrage",
    "heamorrhage",
)

BLEEDING_TOKENS = HEMORRHAGE_TOKENS + (
    "internal bleeding",
    "internal bleed",
    "massive bleed",
    "massive bleeding",
    "severe bleeding",
    "exsanguination",
    "exsanguinating",
    "hematemesis",
    "melena",
    "black stool",
    "coffee ground",
    "coffee-ground",
    "blood loss",
    "bleeding",
    "bleed",
)

SEVERITY_TOKENS = (
    "severe",
    "critical",
    "massive",
    "collapse",
    "unresponsive",
    "deteriorating",
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
    "what do i do",
    "what do we do",
    "what do you do",
    "what do u do",
    "what u do",
    "what should i do",
    "what should we do",
    "what can you do",
    "what can u do",
    "what now",
    "what next",
    "further action",
    "further actions",
    "can you help",
    "thanks",
    "thank you",
)

CAPABILITY_HINTS = (
    "what do you do",
    "what do u do",
    "what can you do",
    "what can u do",
    "who are you",
    "who are u",
    "who r u",
    "capabilities",
    "help",
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
    "breath",
    "breathless",
    "breathl",
    "shortness of breath",
    "headache",
    "head ache",
    "hedache",
    "migraine",
    "speech",
    "language",
    "word finding",
    "word-finding",
    "confusion",
    "slurred speech",
    "dyslex",
)

MEDICAL_TOPIC_HINTS = (
    "disease",
    "condition",
    "illness",
    "syndrome",
    "disorder",
    "infection",
    "viral",
    "bacterial",
    "fungal",
    "pneumonia",
    "asthma",
    "copd",
    "stroke",
    "seizure",
    "epilepsy",
    "heart attack",
    "myocardial infarction",
    "arrhythmia",
    "heart failure",
    "diabetes",
    "hypoglycemia",
    "hyperglycemia",
    "hypertension",
    "blood pressure",
    "kidney",
    "renal",
    "liver",
    "hepatitis",
    "ulcer",
    "gastritis",
    "appendicitis",
    "gallbladder",
    "pancreatitis",
    "urinary tract",
    "uti",
    "sepsis",
    "anaphylaxis",
    "anemia",
    "hemorrhage",
    "haemorrhage",
    "hemorrage",
    "heamorrhage",
    "bleeding",
    "bleed",
    "clot",
    "dvt",
    "pe",
    "embolism",
    "fracture",
    "sprain",
    "arthritis",
    "covid",
    "flu",
    "swelling",
    "weakness",
    "numbness",
    "pregnancy",
    "postpartum",
    "depression",
    "anxiety",
    "overdose",
    "poison",
    "toxin",
)

MEDICAL_RESPONSE_HINTS = CLINICAL_HINTS + MEDICAL_TOPIC_HINTS

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
        return _fallback_chat_reply("", normalized_context)

    if _is_snapshot_request(cleaned):
        snapshot_reply = _snapshot_reply(normalized_context)
        if snapshot_reply:
            return snapshot_reply

    quick_mode = _is_quick_request(cleaned)
    conversational_mode = _is_conversational_request(cleaned)
    clinical_mode = quick_mode or _is_clinical_request(cleaned) or _should_use_clinical_context(cleaned, normalized_context)
    if _is_capability_request(cleaned):
        conversational_mode = True
        clinical_mode = False
    rag_chunks = _retrieve_rag_context(query=_build_rag_query(cleaned, normalized_context), top_k=3) if clinical_mode else []

    # other high-acuity condition shortcuts
    lowered = cleaned.lower()
    hemoptysis_tokens = (
        "hemoptysis",
        "coughing blood",
        "coughing up blood",
        "massive hemoptysis",
        "lung bleeding",
        "lungs bleeding",
        "bleeding in lung",
        "bleeding in lungs",
        "bleeding in the lung",
        "bleeding in the lungs",
        "pulmonary hemorrhage",
    )
    if any(tok in lowered for tok in hemoptysis_tokens) and (any(tok in lowered for tok in SEVERITY_TOKENS) or str(normalized_context.get("status", "")).lower() in {"critical", "warning"}):
        return _structured_emergency_reply_for("hemoptysis", cleaned, normalized_context)

    # Immediate structured emergency reply for severe/internal bleeding requests
    if _is_severe_bleeding_request(lowered, normalized_context):
        return _structured_emergency_reply(cleaned, normalized_context)

    aortic_tokens = ("aortic dissection", "tearing chest pain", "ripping chest pain", "sudden severe chest pain", "sudden severe back pain")
    if any(tok in lowered for tok in aortic_tokens) and (any(tok in lowered for tok in SEVERITY_TOKENS) or str(normalized_context.get("status", "")).lower() in {"critical", "warning"}):
        return _structured_emergency_reply_for("aortic_dissection", cleaned, normalized_context)

    stroke_tokens = ("stroke", "face droop", "slurred speech", "weakness on one side", "arm drift", "speech difficulty", "aphasia", "hemiparesis")
    if any(tok in lowered for tok in stroke_tokens) and (any(tok in lowered for tok in SEVERITY_TOKENS) or str(normalized_context.get("status", "")).lower() in {"critical", "warning"}):
        return _structured_emergency_reply_for("stroke", cleaned, normalized_context)

    if not GEMINI_API_KEY:
        groq_key = os.getenv("GROQ_API_KEY")
        if groq_key:
            try:
                if quick_mode:
                    groq_reply = _generate_quick_chat_reply_via_groq_sync(groq_key, cleaned, normalized_context)
                elif clinical_mode:
                    groq_reply = _generate_chat_reply_via_groq_sync(groq_key, cleaned, normalized_context, rag_chunks)
                else:
                    groq_reply = _generate_conversational_chat_reply_via_groq_sync(groq_key, cleaned)
                return _humanize_chat_reply(groq_reply, cleaned, normalized_context)
            except Exception:
                pass
        if quick_mode:
            return _fallback_quick_reply(normalized_context)
        if clinical_mode:
            return _fallback_chat_reply(cleaned, normalized_context)
        return _fallback_conversational_reply(cleaned)

    try:
        if quick_mode:
            gemini_reply = await asyncio.wait_for(
                asyncio.to_thread(_generate_quick_chat_reply_via_gemini_sync, cleaned, normalized_context),
                timeout=4.0,
            )
        elif clinical_mode:
            gemini_reply = await asyncio.wait_for(
                asyncio.to_thread(_generate_chat_reply_via_gemini_sync, cleaned, normalized_context, rag_chunks),
                timeout=4.0,
            )
        else:
            gemini_reply = await asyncio.wait_for(
                asyncio.to_thread(_generate_conversational_chat_reply_via_gemini_sync, cleaned),
                timeout=4.0,
            )
    except Exception:
        groq_key = os.getenv("GROQ_API_KEY")
        if groq_key:
            try:
                if quick_mode:
                    groq_reply = _generate_quick_chat_reply_via_groq_sync(groq_key, cleaned, normalized_context)
                elif clinical_mode:
                    groq_reply = _generate_chat_reply_via_groq_sync(groq_key, cleaned, normalized_context, rag_chunks)
                else:
                    groq_reply = _generate_conversational_chat_reply_via_groq_sync(groq_key, cleaned)
                return _humanize_chat_reply(groq_reply, cleaned, normalized_context)
            except Exception:
                pass

        if quick_mode:
            return _fallback_quick_reply(normalized_context)
        if clinical_mode:
            return _fallback_chat_reply(cleaned, normalized_context)
        return _fallback_conversational_reply(cleaned)

    # decide whether we require Groq to return a structured 5-line emergency reply
    require_structured = any(tok in cleaned.lower() for tok in SEVERITY_TOKENS) or str(normalized_context.get("status", "")).lower() in {"critical", "warning"}

    final_reply = _maybe_summarize_with_groq(gemini_reply, cleaned, normalized_context, require_structured=require_structured)
    return _humanize_chat_reply(final_reply or gemini_reply, cleaned, normalized_context)


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


def _generate_chat_reply_via_gemini_sync(message: str, context: dict[str, Any], rag_chunks: list[str] | None = None) -> str:
    vitals_summary = _format_vitals_context(context)
    prompt_parts = [
        "You are the REVIVE assistant.",
        "Reply in a natural, human tone like a helpful chatbot.",
        "If the question is general, answer casually and clearly without clinical wording.",
        "If the question is medical, speak like a senior emergency clinician and include practical next steps.",
        "For medical questions, include the likely disease or body system, the safest first-line medicine or medicine class if appropriate, what to do now, and when to call urgent or emergency support.",
        "For severe or unstable cases, explicitly say to call emergency support now.",
        "For mild cases, say what to do at home and what warning signs mean they need urgent care.",
        "Keep the answer concise: usually 2 to 4 short sentences.",
        "Never say you are unavailable, mention fallback behavior, or reference system status.",
        "Do not diagnose or claim definitive treatment authority.",
        f"User message: {message.strip()}",
    ]
    if vitals_summary:
        prompt_parts.append(f"Current dashboard context: {vitals_summary}")
    if rag_chunks:
        prompt_parts.append("Relevant protocol context:")
        prompt_parts.extend(f"- {chunk}" for chunk in rag_chunks[:3])

    prompt = "\n".join(prompt_parts)
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.5, "maxOutputTokens": 220},
    }
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{GEMINI_MODEL}:generateContent?key="
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
            "Never say you are unavailable, mention fallback behavior, or reference system status.",
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
            f"{GEMINI_MODEL}:generateContent?key="
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
            "Never say you are unavailable, mention fallback behavior, or reference system status.",
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
            f"{GEMINI_MODEL}:generateContent?key="
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
        "Never say you are unavailable, mention fallback behavior, or reference system status.",
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
            f"{GEMINI_MODEL}:generateContent?key="
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
            f"{GEMINI_MODEL}:generateContent?key="
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


def _maybe_summarize_with_groq(gemini_reply: str, message: str, context: dict[str, Any], require_structured: bool = False) -> str:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return ""

    try:
        return _summarize_gemini_reply_with_groq_sync(api_key, gemini_reply, message, context, require_structured=require_structured)
    except Exception:
        return ""


def _summarize_gemini_reply_with_groq_sync(
    api_key: str,
    gemini_reply: str,
    message: str,
    context: dict[str, Any],
    require_structured: bool = False,
) -> str:
    from groq import Groq

    client = Groq(api_key=api_key)
    vitals_summary = _format_vitals_context(context)
    status = str(context.get("status", "Unknown")).strip() or "Unknown"
    trend = str(context.get("trend", "stable")).strip() or "stable"

    if require_structured:
        prompt = (
            "You are the final response editor for a medical assistant. "
            "Rewrite the draft into a structured user-facing answer that uses the current snapshot and the assistant draft together. "
            "Make the reply specific about the likely condition, the immediate measures, and the medication or drug class if it is reasonably clear. "
            "Prefer named drugs or drug classes when clinically appropriate, and do not default to generic painkillers unless they are truly the best fit. "
            "If the condition is uncertain, say that the specific drug cannot be chosen safely yet and explain what information is needed. "
            "Do not add new facts. Return exactly 5 short labeled lines: Current snapshot, Status, Actions, Drug, Emergency threshold.\n"
            f"User message: {message.strip()}\n"
            f"Assistant draft: {gemini_reply.strip()}\n"
            f"Current snapshot: {vitals_summary if vitals_summary else 'N/A'}\n"
            f"Status: {status}\n"
            f"Trend: {trend}"
        )
    else:
        prompt = (
            "You are the final response editor for a medical assistant. "
            "Rewrite the draft into the best user-facing answer while keeping the same meaning. "
            "Use the user message and the assistant draft together to make the reply clearer, more helpful, and more specific. "
            "If the answer is already strong, preserve it and only smooth the wording. "
            "Do not add new facts. Return 1 to 3 short sentences, max 40 words.\n"
            f"User message: {message.strip()}\n"
            f"Assistant draft: {gemini_reply.strip()}"
        )

    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": (
                    "You produce the final REVIVE chat reply from the user message and the draft answer. "
                    "Keep the tone human, clinically useful, and concise. Do not mention backend tools or model names. "
                    "Return only the five labeled lines requested by the prompt."
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
    return any(token in lowered for token in MEDICAL_RESPONSE_HINTS)


def _is_capability_request(message: str) -> bool:
    lowered = message.lower()
    return any(token in lowered for token in CAPABILITY_HINTS)


def _is_snapshot_request(message: str) -> bool:
    lowered = message.lower()
    return any(token in lowered for token in SNAPSHOT_HINTS)


def _snapshot_reply(context: dict[str, Any]) -> str:
    if not context:
        return "No vitals are available yet. Share HR, SpO2, movement, status, and trend for a snapshot."

    hr = context.get("hr")
    spo2 = context.get("spo2")
    movement = context.get("movement")
    status = str(context.get("status", "Unknown"))
    trend = str(context.get("trend", "stable"))
    return (
        "Current snapshot: "
        f"HR={hr if hr is not None else 'NA'}, "
        f"SpO2={spo2 if spo2 is not None else 'NA'}, "
        f"Movement={movement if movement is not None else 'NA'}, "
        f"Status={status}, Trend={trend}."
    )


def _is_severe_bleeding_request(message: str, context: dict[str, Any]) -> bool:
    lowered = message.lower()
    if not any(token in lowered for token in BLEEDING_TOKENS):
        return False

    if any(token in lowered for token in HEMORRHAGE_TOKENS):
        return True

    if any(token in lowered for token in SEVERITY_TOKENS):
        return True

    status = str(context.get("status", "")).lower().strip()
    return status in {"critical", "warning"}


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
    if any(token in lowered for token in ("who are you", "who are u", "who r u", "what are you", "your name", "what do you do", "what do u do", "what can you do", "what can u do")):
        return "I am REVIVE Assistant. I can chat normally, explain vitals, and switch into clinical mode when you ask about symptoms or next steps."
    if any(token in lowered for token in ("help", "what can you do", "capabilities")):
        return "I am trained for medical emergencies. Ask me about symptoms, vitals, drugs, red flags, or next steps, and I will keep it practical."
    if any(token in lowered for token in ("hi", "hello", "hey")):
        return "Hi, I am REVIVE Assistant. I am trained for medical emergencies, so ask me about symptoms, vitals, drugs, or next steps."
    if any(token in lowered for token in ("thanks", "thank you")):
        return "You are welcome. I am here whenever you need a quick summary or next-step support."
    return "I am trained for medical emergencies only. Ask me about a disease, symptom, vitals, drug option, red flag, or the next step, and I will answer in plain language."


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
        return _fallback_conversational_reply(trimmed)

    lowered = trimmed.lower()

    if _is_snapshot_request(lowered):
        return _snapshot_reply(context or {})

    if _is_severe_bleeding_request(lowered, context or {}):
        return _structured_emergency_reply(trimmed, context or {})

    if any(token in lowered for token in ("who are you", "who are u", "who r u", "what are you", "what do you do", "what do u do", "what can you do", "what can u do", "help", "hello", "hi", "hey", "thanks", "thank you")):
        return _fallback_conversational_reply(trimmed)

    if any(token in lowered for token in ("pizza", "joke", "movie", "game", "music", "weather", "stock", "crypto", "sports", "politics", "meme", "friend", "girlfriend", "boyfriend")) and not any(token in lowered for token in ("pain", "drug", "medicine", "medication", "fever", "cough", "breath", "headache", "dizzy", "vomit", "rash", "confusion", "symptom", "patient", "disease", "condition", "illness", "diagnosis")):
        return "I am trained for medical emergencies only. Ask me about symptoms, vitals, drug options, red flags, or the next step, and I will keep it useful."

    symptom_responses = [
        (("headache", "head ache", "hedache", "migraine", "thunderclap headache", "worst headache", "sudden headache"), "Severe headache should be treated carefully, especially if it started suddenly or is paired with weakness, confusion, or speech trouble. Keep them resting, reduce stimulation, and get urgent medical review if it is new, severe, or unlike their usual headaches."),
        (("speech trouble", "slurred speech", "word finding", "word-finding", "language trouble", "confusion", "dyslex", "cannot speak", "hard to speak"), "Speech or language trouble with headache can be a red flag. Keep the person safe, note the time symptoms started, and get urgent medical assessment now if this is new or worsening."),
        (("breathless", "breathlessness", "breathl", "shortness of breath", "trouble breathing", "breathing hard", "hard to breathe", "can't breathe", "cannot breathe"), "Severe breathlessness can be urgent. Sit upright, keep calm, check SpO2 if available, and get emergency help now if it is worsening or the person cannot speak in full sentences."),
        (("chest pain", "pressure in chest", "tight chest"), "Chest pain can be urgent, especially with sweating, breathlessness, or pain spreading to the arm or jaw. Keep them resting and escalate quickly if it feels severe."),
        (("shortness of breath", "trouble breathing", "breathing hard", "can't breathe"), "Breathing trouble needs close monitoring. Sit the person upright, watch SpO2, and escalate right away if oxygen levels drop or work of breathing increases."),
        (("fever", "temperature", "running a fever"), "Fever is often manageable, but high fever, confusion, dehydration, or breathing changes need urgent review. Focus on fluids, rest, and trend the vitals."),
        (("headache", "migraine"), "Headache is often less urgent, but sudden severe headache, weakness, confusion, or vision changes need prompt medical review. Monitor for any red flags."),
        (("cough", "wheezing"), "Cough or wheeze should be watched for breathing effort and SpO2 changes. If it is worsening or the person looks distressed, escalate sooner."),
        (("dizziness", "lightheaded", "faint", "fainting"), "Dizziness can point to low blood pressure, dehydration, or poor oxygenation. Lay the person down if needed, recheck vitals, and escalate if they worsen."),
        (("nausea", "vomit", "vomiting"), "Nausea or vomiting can dehydrate quickly. Watch hydration, breathing, and mental status, and escalate if it is persistent or severe."),
        (("abdominal pain", "stomach pain", "belly pain"), "Abdominal pain varies widely, but severe pain, guarding, fever, or vomiting need urgent assessment. Keep monitoring and note any worsening pattern."),
        (("rash", "hives"), "A new rash is often minor, but rash with swelling, breathing trouble, or dizziness can be an emergency. Watch for any airway or circulation changes."),
        (("confusion", "not responding", "altered"), "Confusion or altered behavior is concerning. Check airway, breathing, circulation, and escalate if the person is not improving quickly."),
    ]

    for triggers, response in symptom_responses:
        if any(trigger in lowered for trigger in triggers):
            if context:
                hr = _to_int(context.get("hr"))
                spo2 = _to_int(context.get("spo2"))
                movement = _to_int(context.get("movement"))
                status = str(context.get("status", "Normal"))
                trend = str(context.get("trend", "stable"))
                if spo2 is not None and spo2 < 90:
                    return f"{response} SpO2 is already low, so treat this as urgent and focus on airway, breathing, and escalation now. Current snapshot: HR={hr if hr is not None else 'NA'}, SpO2={spo2}, Movement={movement if movement is not None else 'NA'}, Status={status}, Trend={trend}."
                if hr is not None and (hr < 50 or hr > 130):
                    return f"{response} The heart rate is outside a safe range, so monitor closely and escalate if symptoms are getting worse. Current snapshot: HR={hr}, SpO2={spo2 if spo2 is not None else 'NA'}, Movement={movement if movement is not None else 'NA'}, Status={status}, Trend={trend}."
            return response

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
        if urgency == "low-acuity":
            if any(token in lowered for token in ("headache", "head ache", "hedache", "migraine", "speech", "language", "word finding", "word-finding", "slurred speech", "confusion", "dyslex")):
                return "If this is a severe headache or any new speech or language problem, keep the person resting, note when it started, and get urgent medical assessment if it is sudden, worsening, or paired with weakness or confusion. If you want, I can outline the usual pain-relief options and the red flags to watch for."

            if any(token in lowered for token in ("breath", "breathless", "breathl", "shortness of breath", "trouble breathing", "can't breathe", "cannot breathe")):
                return "If this is breathlessness, stay upright, loosen tight clothing, avoid exertion, and watch for worsening SpO2 or speech difficulty. If it is getting worse, treat it as urgent. I can also walk you through likely rescue meds or next steps if you want."

            return f"Things look steady overall. Keep monitoring the trend, and if you want, I can explain it in plain English or help with next steps. HR={hr if hr is not None else 'NA'}, SpO2={spo2 if spo2 is not None else 'NA'}, Movement={movement if movement is not None else 'NA'}."

        if urgency == "elevated-risk":
            return (
                f"This looks like an early warning pattern rather than an emergency. Watch the trend closely, repeat vitals soon, and be ready to escalate if breathing, perfusion, or alertness worsens. HR={hr if hr is not None else 'NA'}, SpO2={spo2 if spo2 is not None else 'NA'}, Movement={movement if movement is not None else 'NA'}, Trend={trend}."
            )

        return (
            f"This is a high-risk pattern in the {scenario} context with {concern}. Start airway-breathing-circulation checks right away, prepare escalation, and consider emergency procedures and medication support as appropriate for the scenario. HR={hr if hr is not None else 'NA'}, SpO2={spo2 if spo2 is not None else 'NA'}, Movement={movement if movement is not None else 'NA'}, Trend={trend}."
        )

    return "I can chat normally or help with symptoms, vitals, and next steps. Tell me what is happening and I will keep it simple."


def _should_use_clinical_context(message: str, context: dict[str, Any]) -> bool:
    lowered = message.lower()
    status = str(context.get("status", "")).strip().lower()
    hr = _to_int(context.get("hr"))
    spo2 = _to_int(context.get("spo2"))

    if _is_capability_request(lowered):
        return False

    if status in {"critical", "warning"}:
        return True

    if spo2 is not None and spo2 < 94:
        return True

    if hr is not None and (hr < 60 or hr > 110):
        return True

    clinical_prompts = (
        "symptom",
        "pain",
        "headache",
        "head ache",
        "hedache",
        "migraine",
        "speech",
        "language",
        "word finding",
        "word-finding",
        "confusion",
        "slurred speech",
        "dyslex",
        "breathing",
        "cough",
        "fever",
        "headache",
        "dizzy",
        "nausea",
        "vomit",
        "rash",
        "disease",
        "condition",
        "illness",
        "diagnosis",
        "infection",
        "stroke",
        "diabetes",
        "asthma",
        "copd",
        "sepsis",
        "covid",
        "flu",
        "drug",
        "medicine",
        "medication",
        "dose",
        "treatment",
        "next step",
        "further action",
        "further actions",
        "what should",
        "what now",
        "what next",
    )
    if any(token in lowered for token in clinical_prompts):
        return True

    if any(token in lowered for token in ("what do i do", "what do we do", "how should i respond")):
        return False

    return False


def _humanize_chat_reply(reply: str, message: str, context: dict[str, Any]) -> str:
    clean = (reply or "").strip()
    if not clean:
        return _fallback_chat_reply(message, context)

    if _is_snapshot_request(message):
        snapshot_reply = _snapshot_reply(context)
        return snapshot_reply if snapshot_reply else clean

    if any(marker in clean.lower() for marker in ("current snapshot:", "status:", "actions:", "drug:", "emergency threshold:")):
        return clean

    message_low = message.lower().strip()
    if any(token in message_low for token in ("drug", "medicine", "medication", "what can i take", "what should i take", "recommend", "prescribe")):
        return _medical_followup_reply(message_low, context)
    if any(token in message_low for token in ("vomit", "vomiting", "nausea", "bleeding", "internal bleeding", "blood", "hematemesis", "black stool", "melena")):
        return _medical_followup_reply(message_low, context)

    lowered = clean.lower()
    looks_like_template = any(marker in lowered for marker in ("clinical read:", "priority actions:", "current snapshot:"))
    if not looks_like_template:
        return clean

    status = str(context.get("status", "Normal")).strip().lower()
    trend = str(context.get("trend", "stable")).strip().lower()
    hr = _to_int(context.get("hr"))
    spo2 = _to_int(context.get("spo2"))

    if status == "critical" or trend == "critical" or (spo2 is not None and spo2 < 90) or (hr is not None and (hr < 50 or hr > 130)):
        return "This looks urgent. Focus on breathing, circulation, and rapid escalation. If you want, I can also outline likely rescue meds and procedures in plain language."

    if status == "warning" or trend == "declining" or (spo2 is not None and spo2 < 94):
        return "This looks like an early warning pattern. Keep watching the trend, repeat vitals soon, and be ready to escalate if it gets worse."

    return "Things look steady overall. Keep monitoring, and if you want I can explain the vitals in plain English or help with next steps."


def _medical_followup_reply(message: str, context: dict[str, Any]) -> str:
    status = str(context.get("status", "Normal")).strip().lower()
    hr = _to_int(context.get("hr"))
    spo2 = _to_int(context.get("spo2"))

    if any(token in message for token in ("headache", "head ache", "hedache", "migraine")):
        if status == "critical" or (spo2 is not None and spo2 < 94) or (hr is not None and (hr < 50 or hr > 130)):
            return "For a severe headache, I would not just rely on a drug if it is sudden, new, or paired with weakness, confusion, or speech trouble. That needs urgent assessment first. If it is a simple headache and there are no red flags, acetaminophen is usually the safest first option, and ibuprofen can be used only if there is no ulcer, kidney, bleeding, or pregnancy concern."

        return "For a simple headache, acetaminophen is usually the first-line option if the person has no liver disease or allergy. Ibuprofen can also help if there is no ulcer, kidney disease, blood thinner use, or pregnancy concern. If the headache is sudden, severe, or comes with speech trouble, weakness, confusion, or vision changes, escalate instead of treating it as routine."

    if any(token in message for token in ("breath", "breathless", "shortness of breath", "trouble breathing")):
        return "For breathing trouble, I would not suggest random medication. If this is asthma or COPD and they already have a prescribed rescue inhaler, use that as directed. Otherwise keep them upright, minimize exertion, and treat worsening symptoms or low SpO2 as urgent."

    if any(token in message for token in ("fever", "temperature")):
        return "For fever, acetaminophen or ibuprofen may help if the person can take them safely, but the priority is hydration and watching for confusion, breathing changes, or dehydration. If the fever is high or the person looks unwell, get checked."

    if any(token in message for token in ("allergy", "hives", "rash", "itching")):
        return "For a mild allergic rash or itching, a non-drowsy antihistamine is often used if it is safe for the person. If there is swelling of the lips or tongue, wheezing, or trouble breathing, treat it as an emergency instead of waiting."

    if any(token in message for token in ("vomit", "vomiting", "nausea")):
        if any(token in message for token in ("internal bleeding", "bleeding", "blood", "hematemesis", "coffee ground", "coffee-ground", "black stool", "melena", *HEMORRHAGE_TOKENS)):
            return "Vomiting with internal bleeding is an emergency. Keep the person lying down or on their side if they are drowsy, do not give food, alcohol, or painkillers like ibuprofen, and get emergency help now. In hospital, the usual immediate steps are IV access, fluids or blood if needed, anti-nausea medicine such as ondansetron, and urgent evaluation for the bleeding source."

        return "For vomiting, start with small frequent sips of oral rehydration solution or clear fluids if the person can keep them down. If medication is appropriate, an anti-nausea medicine such as ondansetron is commonly used, and in some adults promethazine or metoclopramide may be options depending on age and other conditions. If vomiting is severe, repeated, or mixed with blood or black material, or there is abdominal pain, weakness, confusion, or dehydration, it needs urgent assessment."

    if any(token in message for token in ("cough", "wheezing")):
        return "For cough or wheeze, the right medicine depends on the cause. If this is known asthma, a prescribed rescue inhaler is the first step; otherwise I would watch the breathing rate, SpO2, and whether it is getting worse."

    if any(token in message for token in ("pain", "back pain", "abdominal pain", "stomach pain", "body ache")):
        return "For pain without red flags, acetaminophen is usually the safest starting option, and ibuprofen can help if there is no ulcer, kidney disease, bleeding risk, or pregnancy concern. If the pain is severe, sudden, or localized with fever or vomiting, get it checked first."

    if any(token in message for token in ("disease", "condition", "illness", "diagnosis", "infection", "stroke", "diabetes", "asthma", "copd", "sepsis", "covid", "flu", "heart attack", "kidney", "liver", "anemia", "anaphylaxis", "epilepsy", "seizure", "ulcer", "appendicitis", "pneumonia")):
        return "For a disease question, I can usually give four things: the likely body system involved, the first-line medicine class if it is safe, what to do right now, and the warning signs that mean urgent care or emergency support. If you name the condition, I will make it specific."

    return "Medication choice depends on the symptom, disease, age, allergies, pregnancy, and other conditions. If you tell me the problem in one line, I can give the safest first-line option and the red flags to watch for."


def _structured_emergency_reply(message: str, context: dict[str, Any]) -> str:
    """Return a 5-line structured emergency reply for severe scenarios (snapshot, status, actions, drug, emergency threshold)."""
    hr = context.get("hr")
    spo2 = context.get("spo2")
    movement = context.get("movement")
    status = str(context.get("status", "Unknown"))
    trend = str(context.get("trend", "stable"))

    snapshot = f"HR={hr if hr is not None else 'NA'}, SpO2={spo2 if spo2 is not None else 'NA'}, Movement={movement if movement is not None else 'NA'}, Status={status}, Trend={trend}"

    actions = (
        "Keep airway patent; control external bleeding with firm direct pressure; if internal bleeding suspected, lie the patient flat unless breathing is compromised, avoid oral intake, establish IV large-bore access, prepare for blood products, and arrange urgent surgical/IR evaluation."
    )

    drug = (
        "Tranexamic acid IV if available and appropriate in the clinical setting (early use in major traumatic hemorrhage); avoid NSAIDs or other anticoagulants. Give blood products as indicated by resuscitation protocols."
    )

    emergency = (
        "Call emergency services now and transfer to the nearest trauma center/OR if hemodynamic instability, ongoing hemorrhage, altered mental status, or SpO2<90. Activate massive transfusion protocol where available."
    )

    return (
        f"Current snapshot: {snapshot}\n"
        f"Status: {status}\n"
        f"Actions: {actions}\n"
        f"Drug: {drug}\n"
        f"Emergency threshold: {emergency}"
    )


def _generate_chat_reply_via_groq_sync(
    api_key: str,
    message: str,
    context: dict[str, Any],
    rag_chunks: list[str] | None = None,
) -> str:
    from groq import Groq

    client = Groq(api_key=api_key)
    vitals_summary = _format_vitals_context(context)
    prompt_parts = [
        "You are the REVIVE assistant.",
        "Reply in a natural, human tone like a helpful chatbot.",
        "If the question is general, answer casually and clearly without clinical wording.",
        "If the question is medical, speak like a senior emergency clinician and include practical next steps.",
        "For medical questions, include the likely disease or body system, the safest first-line medicine or medicine class if appropriate, what to do now, and when to call urgent or emergency support.",
        "For severe or unstable cases, explicitly say to call emergency support now.",
        "For mild cases, say what to do at home and what warning signs mean they need urgent care.",
        "Keep the answer concise: usually 2 to 4 short sentences.",
        "Never mention system status or model names.",
        "Do not diagnose or claim definitive treatment authority.",
        f"User message: {message.strip()}",
    ]
    if vitals_summary:
        prompt_parts.append(f"Current dashboard context: {vitals_summary}")
    if rag_chunks:
        prompt_parts.append("Relevant protocol context:")
        prompt_parts.extend(f"- {chunk}" for chunk in rag_chunks[:3])

    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": "Return a concise, clinically useful reply with no references to tools or models.",
            },
            {"role": "user", "content": "\n".join(prompt_parts)},
        ],
        max_tokens=220,
        temperature=0.4,
    )

    content = completion.choices[0].message.content if completion.choices else ""
    return (content or "").strip() or _fallback_chat_reply(message, context)


def _generate_conversational_chat_reply_via_groq_sync(api_key: str, message: str) -> str:
    from groq import Groq

    client = Groq(api_key=api_key)
    prompt = "\n".join(
        [
            "You are the REVIVE assistant.",
            "The user asked a general non-clinical message (identity/help/small talk).",
            "Reply in a warm, human tone.",
            "Keep the answer concise: 1 to 2 short sentences, max 30 words.",
            "Never mention system status or model names.",
            "Do not inject vitals or clinical advice unless the user explicitly asks for it.",
            f"User message: {message.strip()}",
        ]
    )

    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "Return a short, friendly reply."},
            {"role": "user", "content": prompt},
        ],
        max_tokens=120,
        temperature=0.5,
    )

    content = completion.choices[0].message.content if completion.choices else ""
    return (content or "").strip() or _fallback_conversational_reply(message)


def _generate_quick_chat_reply_via_groq_sync(api_key: str, message: str, context: dict[str, Any]) -> str:
    from groq import Groq

    client = Groq(api_key=api_key)
    vitals_summary = _format_vitals_context(context)
    prompt = "\n".join(
        [
            "You are REVIVE emergency copilot.",
            "Use concise senior emergency-clinician communication style.",
            "Do not diagnose. Give protocol-grounded support and explicit escalation cues.",
            "Never mention system status or model names.",
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

    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "Return the five-line format exactly as requested."},
            {"role": "user", "content": prompt},
        ],
        max_tokens=180,
        temperature=0.2,
    )

    content = completion.choices[0].message.content if completion.choices else ""
    return (content or "").strip() or _fallback_quick_reply(context)


def _structured_emergency_reply_for(condition: str, message: str, context: dict[str, Any]) -> str:
    """Return structured replies for named severe conditions."""
    hr = context.get("hr")
    spo2 = context.get("spo2")
    movement = context.get("movement")
    status = str(context.get("status", "Unknown"))
    trend = str(context.get("trend", "stable"))

    snapshot = f"HR={hr if hr is not None else 'NA'}, SpO2={spo2 if spo2 is not None else 'NA'}, Movement={movement if movement is not None else 'NA'}, Status={status}, Trend={trend}"

    if condition == "hemoptysis":
        actions = (
            "Protect airway (consider intubation if large-volume bleeding), position with bleeding lung dependent, suction as needed, call bronchoscopy/thoracic surgery, and arrange urgent imaging and transfer."
        )
        drug = (
            "Consider tranexamic acid IV (e.g., 1 g IV bolus; then 1 g infusion over 8 hours if local protocol permits) while preparing definitive control. Use according to local guidelines."
        )
        emergency = (
            "Call emergency services and transfer urgently for bronchoscopic or surgical control if bleeding persists, airway compromise, hemodynamic instability, or SpO2 falls below 90."
        )
    elif condition == "aortic_dissection":
        actions = (
            "Keep patient calm and still, control pain, lower shear stress on the aorta, obtain urgent CT angiography, and notify cardiothoracic surgery and vascular teams immediately."
        )
        drug = (
            "IV beta-blocker to reduce heart rate and shear (example agents: esmolol or IV boluses of labetalol) as per local protocol; avoid aggressive fluids."
        )
        emergency = (
            "Call emergency/vascular surgery immediately and transfer to definitive care if chest/back pain with syncope, limb ischemia, hypotension, or neurologic deficit."
        )
    elif condition == "stroke":
        actions = (
            "Note time of onset, perform FAST/NIHSS screening, get non-contrast CT head immediately, and activate stroke pathway. Maintain airway and glucose control."
        )
        drug = (
            "Thrombolysis (alteplase) is a time-sensitive option for eligible ischemic stroke patients—do NOT give without stroke team evaluation."
        )
        emergency = (
            "Activate stroke team now and transfer to stroke-ready center if deficits are severe, onset is within thrombolysis window, or patient is deteriorating."
        )
    else:
        return _structured_emergency_reply(message, context)

    return (
        f"Current snapshot: {snapshot}\n"
        f"Status: {status}\n"
        f"Actions: {actions}\n"
        f"Drug: {drug}\n"
        f"Emergency threshold: {emergency}"
    )


def _build_rag_query(message: str, context: dict[str, Any]) -> str:
    parts = [message.strip()]
    for key in ("hr", "spo2", "movement", "status", "trend", "scenario"):
        value = context.get(key)
        if value is not None:
            parts.append(f"{key}={value}")
    return " ".join(parts)


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


def _get_supabase_client() -> Any | None:
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

    local_chunks = _retrieve_local_chunks(query=query, top_k=top_k)
    if _is_web_enrichment_worthy(query):
        web_chunks = _retrieve_web_chunks(query=query, top_k=top_k)
        merged_chunks: list[str] = []
        for chunk in [*web_chunks, *local_chunks]:
            if chunk and chunk not in merged_chunks:
                merged_chunks.append(chunk)
        if merged_chunks:
            return merged_chunks[:top_k]

    return local_chunks


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


def _retrieve_web_chunks(query: str, top_k: int) -> list[str]:
    if not _is_web_enrichment_worthy(query):
        return []

    search_results = _search_web(query=query, max_results=top_k)
    if not search_results:
        return []

    collected_chunks: list[str] = []
    source_records: list[dict[str, Any]] = []

    for result in search_results[:top_k]:
        title = result.get("title", "").strip()
        url = result.get("url", "").strip()
        snippet = result.get("snippet", "").strip()

        page_text = _fetch_webpage_text(url) if url else ""
        candidate_texts = [text for text in [snippet, _first_meaningful_lines(page_text)] if text]
        if not candidate_texts:
            continue

        collected_chunks.extend(candidate_texts[:2])
        source_records.append({"title": title, "url": url, "snippet": snippet})

    if not collected_chunks:
        return []

    _store_web_rag_context(query=query, source_records=source_records, chunks=collected_chunks)
    return collected_chunks[:top_k]


def _is_web_enrichment_worthy(query: str) -> bool:
    lowered = query.lower()
    triggers = (
        "drug",
        "medicine",
        "medication",
        "dose",
        "procedure",
        "disease",
        "condition",
        "illness",
        "treatment",
        "emergency",
        "red flag",
    )
    return any(token in lowered for token in triggers)


def _search_web(query: str, max_results: int = 3) -> list[dict[str, str]]:
    results = _search_web_duckduckgo_json(query=query, max_results=max_results)
    if results:
        return results[:max_results]

    return _search_web_duckduckgo_html(query=query, max_results=max_results)


def _search_web_duckduckgo_json(query: str, max_results: int = 3) -> list[dict[str, str]]:
    api_url = f"https://api.duckduckgo.com/?q={quote_plus(query)}&format=json&no_redirect=1&no_html=1&skip_disambig=1"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    }
    req = request.Request(api_url, headers=headers, method="GET")

    try:
        with request.urlopen(req, timeout=5.0) as response:
            payload = json.loads(response.read().decode("utf-8", errors="ignore"))
    except Exception:
        return []

    results: list[dict[str, str]] = []

    abstract_text = str(payload.get("AbstractText", "") or "").strip()
    abstract_url = str(payload.get("AbstractURL", "") or "").strip()
    abstract_heading = str(payload.get("Heading", "") or "").strip()
    if abstract_text:
        results.append({"title": abstract_heading or query, "snippet": abstract_text, "url": abstract_url})

    def _collect_topics(topics: list[dict[str, Any]]) -> None:
        for topic in topics:
            if len(results) >= max_results:
                return
            if not isinstance(topic, dict):
                continue
            nested = topic.get("Topics")
            if isinstance(nested, list) and nested:
                _collect_topics([item for item in nested if isinstance(item, dict)])
                continue

            text = str(topic.get("Text", "") or "").strip()
            url = str(topic.get("FirstURL", "") or "").strip()
            if not text and not url:
                continue
            title = text.split(" - ", 1)[0].strip() if text else (query or "Web result")
            snippet = text if text else title
            results.append({"title": title, "snippet": snippet, "url": url})

    related_topics = payload.get("RelatedTopics")
    if isinstance(related_topics, list):
        _collect_topics([item for item in related_topics if isinstance(item, dict)])

    seen: set[tuple[str, str]] = set()
    deduped: list[dict[str, str]] = []
    for result in results:
        key = (result.get("title", ""), result.get("snippet", ""))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(result)

    return deduped[:max_results]


def _search_web_duckduckgo_html(query: str, max_results: int = 3) -> list[dict[str, str]]:
    search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    }
    req = request.Request(search_url, headers=headers, method="GET")

    try:
        with request.urlopen(req, timeout=5.0) as response:
            html_text = response.read().decode("utf-8", errors="ignore")
    except Exception:
        return []

    blocks = re.findall(r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?<a[^>]*class="result__snippet"[^>]*>(.*?)</a>', html_text, re.DOTALL)
    results: list[dict[str, str]] = []
    for raw_url, raw_title, raw_snippet in blocks[:max_results]:
        title = _strip_html(raw_title)
        snippet = _strip_html(raw_snippet)
        url = _normalize_duckduckgo_url(raw_url)
        if title or snippet or url:
            results.append({"title": title, "snippet": snippet, "url": url})

    return results


def _normalize_duckduckgo_url(raw_url: str) -> str:
    if raw_url.startswith("//"):
        return f"https:{raw_url}"
    if raw_url.startswith("http://") or raw_url.startswith("https://"):
        return raw_url
    parsed = urlsplit(raw_url)
    if parsed.scheme:
        return raw_url
    return urljoin("https://duckduckgo.com", raw_url)


def _fetch_webpage_text(url: str) -> str:
    if not url or not url.startswith(("http://", "https://")):
        return ""

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    }
    req = request.Request(url, headers=headers, method="GET")

    try:
        with request.urlopen(req, timeout=5.0) as response:
            html_text = response.read().decode("utf-8", errors="ignore")
    except Exception:
        return ""

    return _first_meaningful_lines(html_text)


def _first_meaningful_lines(html_text: str) -> str:
    if not html_text:
        return ""

    cleaned = re.sub(r"(?is)<script.*?>.*?</script>", " ", html_text)
    cleaned = re.sub(r"(?is)<style.*?>.*?</style>", " ", cleaned)
    cleaned = re.sub(r"(?is)<noscript.*?>.*?</noscript>", " ", cleaned)
    cleaned = re.sub(r"(?is)<[^>]+>", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return ""

    return cleaned[:1600]


def _strip_html(text: str) -> str:
    cleaned = re.sub(r"<[^>]+>", " ", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _store_web_rag_context(query: str, source_records: list[dict[str, Any]], chunks: list[str]) -> None:
    client = _get_supabase_client()
    if client is None or not source_records:
        return

    normalized_query = re.sub(r"\s+", " ", query.strip().lower())
    query_hash = hashlib.sha1(normalized_query.encode("utf-8")).hexdigest()[:12]
    title = f"Web Guidance {query_hash}"
    body = "\n\n".join(chunks[:5])[:8000]
    metadata = {
        "source": "web",
        "query": query,
        "records": source_records[:3],
    }

    def _insert() -> None:
        client.table("rag_documents").upsert(
            {
                "title": title,
                "protocol_type": "web",
                "body": body,
                "metadata": metadata,
            },
            on_conflict="title",
        ).execute()

        existing = client.table("rag_documents").select("id").eq("title", title).limit(1).execute()
        rows = existing.data or []
        if not rows:
            return

        document_id = rows[0].get("id")
        if not document_id:
            return

        for index, chunk in enumerate(chunks[:5]):
            client.table("rag_chunks").upsert(
                {
                    "document_id": document_id,
                    "chunk_index": index,
                    "chunk_text": chunk[:4000],
                    "embedding": None,
                    "metadata": {"source": "web", "query": query, "record_index": index},
                },
                on_conflict="document_id,chunk_index",
            ).execute()

    try:
        asyncio.create_task(asyncio.to_thread(_insert))
    except RuntimeError:
        try:
            _insert()
        except Exception:
            return


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
