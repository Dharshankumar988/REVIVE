import asyncio
import os
import re
from typing import Any

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

DEFAULT_INSTANT_ACTION = "Critical vitals detected. Start emergency assessment and monitor airway, breathing, and circulation."
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
_SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
_SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
_SUPABASE_CLIENT: Client | None = None

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
        return await asyncio.wait_for(
            asyncio.to_thread(_generate_via_groq_sync, api_key, vitals),
            timeout=1.2,
        )
    except Exception:
        return _default_action_from_vitals(vitals)


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


def generate_detailed_steps(vitals: dict[str, Any]) -> list[str]:
    """Return three concise, retrieval-backed response steps.

    Retrieval order:
    1) Supabase RAG chunks via text search RPC.
    2) Local fallback corpus if remote RAG is unavailable or empty.
    """
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

    if rag_chunks:
        # Inject one retrieval-grounded line to keep the guidance tied to protocol text.
        retrieved_line = _sentence_from_chunk(rag_chunks[0])
        if retrieved_line:
            base_steps[1] = retrieved_line

    return base_steps[:3]


def _default_action_from_vitals(vitals: dict[str, Any]) -> str:
    spo2 = int(vitals.get("spo2", 0) or 0)
    hr = int(vitals.get("hr", 0) or 0)

    if spo2 < 90:
        return "Critical SpO2 detected. Sit patient upright and monitor breathing closely."
    if hr < 50:
        return "Critical heart rate detected. Check pulse immediately and prepare emergency response."

    return DEFAULT_INSTANT_ACTION


def _get_supabase_client() -> Client | None:
    global _SUPABASE_CLIENT

    if _SUPABASE_CLIENT is not None:
        return _SUPABASE_CLIENT

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
